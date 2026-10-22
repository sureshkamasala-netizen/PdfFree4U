import hashlib
import base64
import io
import json
import math
import os
import re
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz
from flask import Flask, Response, abort, jsonify, render_template, request, send_file, session
from PIL import Image
from pypdf import PdfReader, PdfWriter
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_PAGE_COUNT = 1500
OUTPUT_RETENTION = timedelta(hours=24)
ALLOWED_TOOLS = {
    "merge",
    "split",
    "compress",
    "rotate",
    "images-to-pdf",
    "protect",
    "unlock",
    "remove-pages",
    "extract-pages",
    "rearrange-pages",
    "pdf-to-images",
    "extract-pdf-images",
    "pdf-ocr",
    "add-watermark",
    "add-page-numbers",
    "pdf-overlay",
    "compare-pdfs",
    "web-optimizer",
    "redact-pdf",
    "create-pdf",
    "edit-pdf",
    "sign-pdf",
    "pdf-converter",
}
TOOL_ALIASES = {
    "merge-pdf": "merge",
    "merge": "merge",
    "split-pdf": "split",
    "split": "split",
    "compress-pdf": "compress",
    "compress": "compress",
    "rotate-pdf": "rotate",
    "rotate-pdf-pages": "rotate",
    "rotate": "rotate",
    "images-to-pdf": "images-to-pdf",
    "image-to-pdf": "images-to-pdf",
    "jpg-to-pdf": "images-to-pdf",
    "png-to-pdf": "images-to-pdf",
    "create-pdf": "create-pdf",
    "protect-pdf": "protect",
    "protect": "protect",
    "unlock-pdf": "unlock",
    "unlock": "unlock",
    "remove-pdf-pages": "remove-pages",
    "remove-pages": "remove-pages",
    "extract-pdf-pages": "extract-pages",
    "extract-pages": "extract-pages",
    "rearrange-pdf-pages": "rearrange-pages",
    "rearrange-pages": "rearrange-pages",
    "pdf-to-images": "pdf-to-images",
    "pdf-to-image": "pdf-to-images",
    "extract-pdf-images": "extract-pdf-images",
    "extract-images": "extract-pdf-images",
    "pdf-ocr": "pdf-ocr",
    "ocr-pdf": "pdf-ocr",
    "add-watermark": "add-watermark",
    "watermark-pdf": "add-watermark",
    "add-page-numbers": "add-page-numbers",
    "page-numbers": "add-page-numbers",
    "pdf-overlay": "pdf-overlay",
    "overlay-pdf": "pdf-overlay",
    "compare-pdfs": "compare-pdfs",
    "compare-pdf": "compare-pdfs",
    "web-optimizer": "web-optimizer",
    "web-optimize-pdf": "web-optimizer",
    "redact-pdf": "redact-pdf",
    "redact": "redact-pdf",
    "sign-pdf": "sign-pdf",
    "sign": "sign-pdf",
    "edit-pdf": "edit-pdf",
    "edit": "edit-pdf",
    "pdf-converter": "pdf-converter",
    "convert-pdf": "pdf-converter",
}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key-change-me"),
    MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
    DATABASE_PATH=os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "jobs.sqlite3")),
    OUTPUT_DIR=os.environ.get("OUTPUT_DIR", str(BASE_DIR / "instance" / "outputs")),
)


@contextmanager
def database_connection():
    path = Path(app.config["DATABASE_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database():
    with database_connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                output_name TEXT NOT NULL,
                output_path TEXT NOT NULL,
                input_bytes INTEGER NOT NULL,
                output_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS jobs_owner_created ON jobs(owner_id, created_at DESC)")


def current_owner_id():
    if "owner_id" not in session:
        session["owner_id"] = uuid.uuid4().hex
    return session["owner_id"]


def normalize_tool(tool):
    if tool is None:
        return ""
    normalized = str(tool).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return TOOL_ALIASES.get(normalized, normalized)


def read_upload(upload, expected_extension=".pdf"):
    filename = secure_filename(upload.filename or "")
    if not filename or Path(filename).suffix.lower() != expected_extension:
        raise ValueError(f"Choose a {expected_extension.lstrip('.').upper()} file.")
    content = upload.read()
    if not content:
        raise ValueError(f"{filename} is empty.")
    if expected_extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError(f"{filename} is not a valid PDF file.")
    return filename, content


def parse_page_ranges(value, page_count):
    if not value or not value.strip():
        return [[page_number] for page_number in range(page_count)]
    groups = []
    seen = set()
    for part in value.split(","):
        if not part.strip():
            continue
        bounds = [segment.strip() for segment in part.strip().split("-")]
        if len(bounds) > 2 or not all(bound.isdigit() for bound in bounds):
            raise ValueError("Use page numbers like 1-3, 5, 8-9.")
        start = int(bounds[0])
        end = int(bounds[-1])
        if start < 1 or end < start or end > page_count:
            raise ValueError(f"Page ranges must be between 1 and {page_count}.")
        pages = list(range(start - 1, end))
        if any(page in seen for page in pages):
            raise ValueError("A page cannot appear in more than one split range.")
        seen.update(pages)
        groups.append(pages)
    if not groups:
        return [[page_number] for page_number in range(page_count)]
    return groups


def parse_page_list(value, page_count):
    if not value or not value.strip():
        return list(range(page_count))
    pages = []
    seen = set()
    for part in value.split(","):
        if not part.strip():
            continue
        bounds = [segment.strip() for segment in part.strip().split("-")]
        if len(bounds) > 2 or not all(bound.isdigit() for bound in bounds):
            raise ValueError("Use page numbers like 1-3, 5, 8-9.")
        start = int(bounds[0])
        end = int(bounds[-1])
        if start < 1 or end < start or end > page_count:
            raise ValueError(f"Page numbers must be between 1 and {page_count}.")
        selection = list(range(start - 1, end))
        for page_index in selection:
            if page_index not in seen:
                seen.add(page_index)
                pages.append(page_index)
    if not pages:
        raise ValueError("Choose at least one page.")
    return pages


def editor_coordinate(value):
    try:
        coordinate = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("The editor sent an invalid position.") from error
    if not math.isfinite(coordinate) or not 0 <= coordinate <= 1:
        raise ValueError("The editor sent an invalid position.")
    return coordinate


def editor_color(value):
    color = str(value or "#18345b")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Choose a valid annotation color.")
    return tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))


def _write_compressed_candidate(content, strength, output_path):
    document = fitz.open(stream=content, filetype="pdf")
    try:
        if strength:
            image_xrefs = {
                image[0]
                for page in document
                for image in page.get_images(full=True)
                if image[0] > 0
            }
            image_scale = 1 - (strength / 100) * 0.45
            jpeg_quality = max(52, min(96, round(98 - strength * 0.48)))

            for xref in image_xrefs:
                extracted = document.extract_image(xref)
                if not extracted:
                    continue
                try:
                    with Image.open(io.BytesIO(extracted["image"])) as source_image:
                        if source_image.width * source_image.height > 60_000_000:
                            continue
                        source_image.load()
                        dimensions = (
                            max(1, round(source_image.width * image_scale)),
                            max(1, round(source_image.height * image_scale)),
                        )
                        if dimensions != source_image.size:
                            source_image = source_image.resize(dimensions, Image.Resampling.LANCZOS)
                        has_alpha = source_image.mode in {"RGBA", "LA"} or "transparency" in source_image.info
                        image_output = io.BytesIO()
                        if has_alpha:
                            source_image.convert("RGBA").save(
                                image_output,
                                format="PNG",
                                optimize=True,
                                compress_level=min(9, max(1, round(strength / 10))),
                            )
                        else:
                            source_image.convert("RGB").save(
                                image_output,
                                format="JPEG",
                                quality=jpeg_quality,
                                optimize=True,
                                progressive=True,
                            )
                        document[0].replace_image(xref, stream=image_output.getvalue())
                except (KeyError, OSError, ValueError, RuntimeError):
                    continue

        document.save(
            output_path,
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
            use_objstms=1,
        )
    finally:
        document.close()


def compress_pdf(content, target_reduction, output_path):
    target_size = len(content) * (1 - target_reduction / 100)
    best_content = content
    best_distance = float(target_reduction)
    low = 0
    high = 100
    with tempfile.TemporaryDirectory() as temporary_directory:
        candidate_path = Path(temporary_directory) / "candidate.pdf"
        while low <= high:
            strength = (low + high) // 2
            _write_compressed_candidate(content, strength, candidate_path)
            candidate = candidate_path.read_bytes()
            actual_reduction = 100 * (len(content) - len(candidate)) / len(content)
            distance = abs(actual_reduction - target_reduction)
            if distance < best_distance:
                best_distance = distance
                best_content = candidate
            if actual_reduction < target_reduction:
                low = strength + 1
            else:
                high = strength - 1
    output_path.write_bytes(best_content)


def apply_editor_operations(document, operations):
    if not isinstance(operations, list) or not operations:
        raise ValueError("Add at least one edit before saving.")
    if len(operations) > 300:
        raise ValueError("A PDF can contain at most 300 editor marks per save.")

    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("The editor sent an invalid operation.")
        try:
            page_index = int(operation.get("page", -1))
        except (TypeError, ValueError) as error:
            raise ValueError("The editor sent an invalid page number.") from error
        if not 0 <= page_index < document.page_count:
            raise ValueError("An edit refers to a page outside this PDF.")

        page = document[page_index]
        page_width = page.rect.width
        page_height = page.rect.height
        kind = str(operation.get("type", ""))
        color = editor_color(operation.get("color"))
        x = editor_coordinate(operation.get("x"))
        y = editor_coordinate(operation.get("y"))
        x2 = editor_coordinate(operation.get("x2", x))
        y2 = editor_coordinate(operation.get("y2", y))
        start = fitz.Point(x * page_width, y * page_height)
        end = fitz.Point(x2 * page_width, y2 * page_height)
        rect = fitz.Rect(min(start.x, end.x), min(start.y, end.y), max(start.x, end.x), max(start.y, end.y))
        width = max(1, min(12, float(operation.get("width", 2))))

        if kind == "text":
            text = str(operation.get("text", "")).strip()
            if not text or len(text) > 1000:
                raise ValueError("Text annotations must contain between 1 and 1000 characters.")
            try:
                font_size = int(operation.get("font_size", 18))
            except (TypeError, ValueError) as error:
                raise ValueError("Text size must be between 8 and 72 points.") from error
            if not 8 <= font_size <= 72:
                raise ValueError("Text size must be between 8 and 72 points.")
            box_height = max(60, font_size * 3)
            top = min(start.y, page_height - box_height - 18)
            text_box = fitz.Rect(start.x, max(18, top), page_width - 24, max(18, top) + box_height)
            remaining = page.insert_textbox(text_box, text, fontsize=font_size, color=color, overlay=True)
            if remaining < 0:
                raise ValueError("The text does not fit on this page. Try shorter text or a smaller size.")
        elif kind in {"rectangle", "circle", "arrow"}:
            if rect.width < 2 or rect.height < 2:
                raise ValueError("Draw a larger shape on the page.")
            if kind == "rectangle":
                page.draw_rect(rect, color=color, width=width, overlay=True)
            elif kind == "circle":
                page.draw_oval(rect, color=color, width=width, overlay=True)
            else:
                page.draw_line(start, end, color=color, width=width, overlay=True)
                angle = math.atan2(end.y - start.y, end.x - start.x)
                head_length = min(14, max(7, rect.width * 0.08))
                wing = math.pi / 7
                left = fitz.Point(end.x - head_length * math.cos(angle - wing), end.y - head_length * math.sin(angle - wing))
                right = fitz.Point(end.x - head_length * math.cos(angle + wing), end.y - head_length * math.sin(angle + wing))
                page.draw_polyline([end, left, right, end], color=color, width=width, overlay=True)
        elif kind in {"freehand", "signature"}:
            raw_points = operation.get("points")
            if not isinstance(raw_points, list) or not 2 <= len(raw_points) <= 3000:
                raise ValueError("A drawn stroke must contain between 2 and 3000 points.")
            points = []
            for point in raw_points:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError("The editor sent an invalid freehand stroke.")
                points.append(fitz.Point(editor_coordinate(point[0]) * page_width, editor_coordinate(point[1]) * page_height))
            page.draw_polyline(points, color=color, width=width, overlay=True)
        elif kind == "image":
            encoded = str(operation.get("data", ""))
            if encoded.startswith("data:"):
                media_type, separator, encoded = encoded.partition(",")
                if not separator or not media_type.startswith(("data:image/png;", "data:image/jpeg;")):
                    raise ValueError("Choose a valid PNG or JPEG image.")
            if len(encoded) > 12 * 1024 * 1024:
                raise ValueError("Images added to a PDF must be smaller than 9 MB.")
            try:
                image_data = base64.b64decode(encoded, validate=True)
                with Image.open(io.BytesIO(image_data)) as image:
                    if image.width * image.height > 50_000_000:
                        raise ValueError("The image is too large to add safely.")
                    image.verify()
            except (ValueError, OSError) as error:
                raise ValueError("Choose a valid PNG or JPEG image.") from error
            if rect.width < 12 or rect.height < 12:
                raise ValueError("Drag to draw a larger image area on the page.")
            page.insert_image(rect, stream=image_data, overlay=True)
        else:
            raise ValueError("The editor sent an unsupported operation.")


def process_job(tool, uploads, options, output_path):
    tool = normalize_tool(tool)

    if tool == "images-to-pdf":
        if not uploads:
            raise ValueError("Choose at least one JPG or PNG image.")
        document = fitz.open()
        total_bytes = 0
        for upload in uploads:
            extension = Path(upload.filename or "").suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png"}:
                raise ValueError("Image to PDF supports JPG and PNG files.")
            filename, content = read_upload(upload, extension)
            total_bytes += len(content)
            if total_bytes > MAX_UPLOAD_BYTES:
                raise ValueError("The total upload is larger than 100 MB.")
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 60_000_000:
                    raise ValueError(f"{filename} is too large to process safely.")
                image.load()
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                page = document.new_page(width=image.width, height=image.height)
                page.insert_image(page.rect, stream=content)
        document.save(output_path, garbage=4, deflate=True)
        document.close()
        return "images.pdf", total_bytes

    if tool == "create-pdf":
        if not uploads:
            raise ValueError("Choose at least one JPG/PNG image or a PDF to create from.")
        pdf_files = []
        image_files = []
        for upload in uploads:
            extension = Path(upload.filename or "").suffix.lower()
            if extension in {".jpg", ".jpeg", ".png"}:
                image_files.append(upload)
            elif extension == ".pdf":
                pdf_files.append(upload)
            else:
                raise ValueError("Create PDF accepts JPG/PNG images or PDF files.")
        if image_files:
            return process_job("images-to-pdf", image_files, options, output_path)
        if len(pdf_files) == 1:
            return process_job("merge", pdf_files, options, output_path)
        if len(pdf_files) > 1:
            return process_job("merge", pdf_files, options, output_path)
        raise ValueError("Choose at least one JPG/PNG image or PDF file.")

    if not uploads:
        raise ValueError("Choose at least one PDF file.")
    input_files = [read_upload(upload) for upload in uploads]
    total_bytes = sum(len(content) for _, content in input_files)
    if total_bytes > MAX_UPLOAD_BYTES:
        raise ValueError("The total upload is larger than 100 MB.")

    readers = []
    for filename, content in input_files:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            if tool != "unlock":
                raise ValueError(f"{filename} is password-protected. Unlock it before processing.")
            password = str(options.get("password", "")).strip()
            if not password:
                raise ValueError("Enter the PDF password to unlock the document.")
            result = reader.decrypt(password)
            if result == 0:
                raise ValueError(f"{filename} is encrypted and the password did not match.")
        if len(reader.pages) == 0:
            raise ValueError(f"{filename} has no pages.")
        if len(reader.pages) > MAX_PAGE_COUNT:
            raise ValueError(f"{filename} exceeds the {MAX_PAGE_COUNT}-page limit.")
        readers.append(reader)

    if tool == "merge":
        if len(readers) < 2:
            raise ValueError("Add at least two PDF files to merge.")
        if sum(len(reader.pages) for reader in readers) > MAX_PAGE_COUNT:
            raise ValueError(f"Merged files cannot exceed {MAX_PAGE_COUNT} pages.")
        writer = PdfWriter()
        for reader in readers:
            writer.append(reader)
        with output_path.open("wb") as output:
            writer.write(output)
        return "merged.pdf", total_bytes

    if tool == "protect":
        if len(readers) != 1:
            raise ValueError("This tool works with one PDF at a time.")
        password = str(options.get("password", "")).strip()
        if not password:
            raise ValueError("Choose a password to protect this PDF.")
        writer = PdfWriter()
        for page in readers[0].pages:
            writer.add_page(page)
        writer.encrypt(user_password=password, owner_password=None, use_128bit=True)
        with output_path.open("wb") as output:
            writer.write(output)
        return "protected.pdf", total_bytes

    if tool == "unlock":
        if len(readers) != 1:
            raise ValueError("This tool works with one PDF at a time.")
        password = str(options.get("password", "")).strip()
        if not password:
            raise ValueError("Enter the PDF password to unlock the document.")
        if readers[0].is_encrypted and readers[0].decrypt(password) == 0:
            raise ValueError("The PDF password is incorrect.")
        writer = PdfWriter()
        for page in readers[0].pages:
            writer.add_page(page)
        with output_path.open("wb") as output:
            writer.write(output)
        return "unlocked.pdf", total_bytes

    if len(readers) != 1:
        raise ValueError("This tool works with one PDF at a time.")

    reader = readers[0]
    if tool == "split":
        ranges = parse_page_ranges(options.get("ranges", ""), len(reader.pages))
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, pages in enumerate(ranges, start=1):
                writer = PdfWriter()
                for page_index in pages:
                    writer.add_page(reader.pages[page_index])
                page_output = io.BytesIO()
                writer.write(page_output)
                archive.writestr(f"pages_{index:02d}.pdf", page_output.getvalue())
        return "split-pages.zip", total_bytes

    if tool in {"compress", "web-optimizer"}:
        if tool == "compress":
            try:
                target_reduction = int(options.get("target_reduction_percent", "85"))
            except (TypeError, ValueError) as error:
                raise ValueError("Target reduction must be between 10% and 90%.") from error
            if not 10 <= target_reduction <= 90:
                raise ValueError("Target reduction must be between 10% and 90%.")
        else:
            target_reduction = 60
        compress_pdf(input_files[0][1], target_reduction, output_path)
        return "compressed.pdf", total_bytes

    if tool == "rotate":
        try:
            degrees = int(options.get("degrees", "90"))
        except ValueError as error:
            raise ValueError("Choose a rotation of 90, 180, or 270 degrees.") from error
        if degrees not in {90, 180, 270}:
            raise ValueError("Choose a rotation of 90, 180, or 270 degrees.")
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(degrees)
            writer.add_page(page)
        with output_path.open("wb") as output:
            writer.write(output)
        return "rotated.pdf", total_bytes

    if tool in {"remove-pages", "extract-pages", "rearrange-pages"}:
        page_indexes = parse_page_list(options.get("ranges", ""), len(reader.pages))
        if tool == "remove-pages":
            keep = [index for index in range(len(reader.pages)) if index not in set(page_indexes)]
            if not keep:
                raise ValueError("Keep at least one page in the PDF.")
            writer = PdfWriter()
            for index in keep:
                writer.add_page(reader.pages[index])
            with output_path.open("wb") as output:
                writer.write(output)
            return "pages-removed.pdf", total_bytes
        if tool == "extract-pages":
            writer = PdfWriter()
            for index in page_indexes:
                writer.add_page(reader.pages[index])
            with output_path.open("wb") as output:
                writer.write(output)
            return "pages-extracted.pdf", total_bytes
        writer = PdfWriter()
        for index in page_indexes:
            writer.add_page(reader.pages[index])
        with output_path.open("wb") as output:
            writer.write(output)
        return "pages-rearranged.pdf", total_bytes

    if tool == "pdf-to-images":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, page in enumerate(document, start=1):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                archive.writestr(f"page_{index:02d}.png", pix.tobytes("png"))
        document.close()
        return "pages.zip", total_bytes

    if tool == "extract-pdf-images":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            image_count = 0
            for page_index, page in enumerate(document, start=1):
                for image_index, img in enumerate(page.get_images(full=True), start=1):
                    xref = img[0]
                    try:
                        pix = fitz.Pixmap(document, xref)
                    except RuntimeError:
                        continue
                    image_count += 1
                    archive.writestr(f"image_{page_index}_{image_index}.png", pix.tobytes("png"))
            if image_count == 0:
                raise ValueError("This PDF does not contain any embedded images.")
        document.close()
        return "images.zip", total_bytes

    if tool == "pdf-ocr":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        text = "\n".join(page.get_text("text").strip() for page in document if page.get_text("text").strip())
        if not text:
            text = "No selectable text was found in this PDF. This demo extracted the page text only."
        output_path.write_text(text, encoding="utf-8")
        return "ocr.txt", total_bytes

    if tool == "add-watermark":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        watermark_text = str(options.get("watermark", "CONFIDENTIAL")).strip() or "CONFIDENTIAL"
        for page in document:
            page.insert_textbox(
                fitz.Rect(80, 140, page.rect.width - 40, page.rect.height - 40),
                watermark_text,
                fontsize=28,
                color=(0.3, 0.3, 0.3),
                rotate=45,
                overlay=True,
            )
        document.save(output_path, garbage=4, deflate=True, clean=True)
        document.close()
        return "watermarked.pdf", total_bytes

    if tool == "add-page-numbers":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        for index, page in enumerate(document, start=1):
            page.insert_textbox(
                fitz.Rect(50, page.rect.height - 40, page.rect.width - 50, page.rect.height),
                str(index),
                fontsize=12,
                color=(0.3, 0.3, 0.3),
                align=1,
                overlay=True,
            )
        document.save(output_path, garbage=4, deflate=True, clean=True)
        document.close()
        return "page-numbers.pdf", total_bytes

    if tool == "redact-pdf":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        for page in document:
            rect = fitz.Rect(40, 40, page.rect.width - 40, page.rect.height - 40)
            page.draw_rect(rect, fill=(0, 0, 0), overlay=True)
        document.save(output_path, garbage=4, deflate=True, clean=True)
        document.close()
        return "redacted.pdf", total_bytes

    if tool == "pdf-overlay":
        if len(readers) != 2:
            raise ValueError("Choose a base PDF and a second PDF to overlay.")
        base = fitz.open(stream=input_files[0][1], filetype="pdf")
        overlay_doc = fitz.open(stream=input_files[1][1], filetype="pdf")
        for page_number, page in enumerate(base):
            overlay_page = overlay_doc[page_number % len(overlay_doc)]
            page.show_pdf_page(page.rect, overlay_doc, overlay_page.number, overlay=True)
        base.save(output_path, garbage=4, deflate=True, clean=True)
        base.close()
        overlay_doc.close()
        return "overlay.pdf", total_bytes

    if tool == "compare-pdfs":
        if len(readers) != 2:
            raise ValueError("Choose two PDF files to compare.")
        lines = [
            "PDF Comparison Report",
            "====================",
            f"Left pages: {len(readers[0].pages)}",
            f"Right pages: {len(readers[1].pages)}",
            f"Left sha256: {hashlib.sha256(input_files[0][1]).hexdigest()}",
            f"Right sha256: {hashlib.sha256(input_files[1][1]).hexdigest()}",
            "Status: files are ready for review.",
        ]
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return "comparison-report.txt", total_bytes

    if tool in {"edit-pdf", "sign-pdf"}:
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        serialized_operations = options.get("edit_operations", "")
        if serialized_operations:
            try:
                operations = json.loads(serialized_operations)
            except (TypeError, json.JSONDecodeError) as error:
                document.close()
                raise ValueError("The editor sent invalid edit data.") from error
            try:
                if tool == "sign-pdf" and (
                    not isinstance(operations, list)
                    or not operations
                    or any(not isinstance(operation, dict) or operation.get("type") != "signature" for operation in operations)
                ):
                    raise ValueError("Draw your signature on the PDF before saving.")
                apply_editor_operations(document, operations)
                document.save(output_path, garbage=4, deflate=True, clean=True)
            finally:
                document.close()
            return ("signed.pdf" if tool == "sign-pdf" else "edited.pdf"), total_bytes

        if tool == "sign-pdf":
            document.close()
            raise ValueError("Draw your signature on the PDF before saving.")

        pages = parse_page_list(str(options.get("edit_pages", "")), len(document))
        edit_mode = str(options.get("edit_mode", "add"))

        if edit_mode == "add":
            text = str(options.get("edit_text", "")).strip()
            if not text:
                raise ValueError("Enter the text you want to add.")
            try:
                font_size = int(options.get("edit_font_size", "18"))
            except (TypeError, ValueError) as error:
                raise ValueError("Text size must be a number from 8 to 72.") from error
            if not 8 <= font_size <= 72:
                raise ValueError("Text size must be a number from 8 to 72.")

            placement = str(options.get("edit_position", "top-left"))
            positions = {
                "top-left": (fitz.TEXT_ALIGN_LEFT, True),
                "top-center": (fitz.TEXT_ALIGN_CENTER, True),
                "top-right": (fitz.TEXT_ALIGN_RIGHT, True),
                "bottom-left": (fitz.TEXT_ALIGN_LEFT, False),
                "bottom-center": (fitz.TEXT_ALIGN_CENTER, False),
                "bottom-right": (fitz.TEXT_ALIGN_RIGHT, False),
            }
            if placement not in positions:
                raise ValueError("Choose a valid text placement.")
            alignment, at_top = positions[placement]
            for page_index in pages:
                page = document[page_index]
                margin = 42
                box_height = max(72, font_size * 3)
                top = margin if at_top else page.rect.height - margin - box_height
                text_box = fitz.Rect(margin, top, page.rect.width - margin, top + box_height)
                remaining = page.insert_textbox(
                    text_box,
                    text,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0.08, 0.14, 0.25),
                    align=alignment,
                    overlay=True,
                )
                if remaining < 0:
                    raise ValueError(f"The text does not fit on page {page_index + 1}. Use a smaller size or shorter text.")
        elif edit_mode == "replace":
            find_text = str(options.get("edit_find_text", "")).strip()
            replacement_text = str(options.get("edit_replacement_text", ""))
            if not find_text:
                raise ValueError("Enter the text you want to find in the PDF.")

            matches_by_page = {}
            for page_index in pages:
                matches = document[page_index].search_for(find_text)
                if matches:
                    matches_by_page[page_index] = matches
                    for match in matches:
                        document[page_index].add_redact_annot(match, fill=(1, 1, 1))
            if not matches_by_page:
                raise ValueError("That text was not found on the selected pages.")

            for page_index, matches in matches_by_page.items():
                page = document[page_index]
                page.apply_redactions()
                if replacement_text.strip():
                    for match in matches:
                        text_box = fitz.Rect(match.x0, match.y0 - 1, match.x1, match.y1 + 1)
                        initial_size = max(6, min(18, int(match.height * 0.72)))
                        inserted = False
                        for font_size in range(initial_size, 5, -1):
                            remaining = page.insert_textbox(
                                text_box,
                                replacement_text,
                                fontsize=font_size,
                                fontname="helv",
                                color=(0.08, 0.14, 0.25),
                                overlay=True,
                            )
                            if remaining >= 0:
                                inserted = True
                                break
                        if not inserted:
                            raise ValueError("Replacement text does not fit the original space. Try shorter text.")
        else:
            raise ValueError("Choose whether to add or replace PDF text.")

        document.save(output_path, garbage=4, deflate=True, clean=True)
        document.close()
        return "edited.pdf", total_bytes

    if tool == "pdf-converter":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        page = document[0]
        page.insert_textbox(fitz.Rect(60, 60, 220, 120), "Converted", fontsize=20, color=(0, 0, 0), overlay=True)
        document.save(output_path, garbage=4, deflate=True, clean=True)
        document.close()
        return "edited.pdf", total_bytes

    raise ValueError("That PDF tool is not available.")


def purge_expired_outputs():
    cutoff = (datetime.now(timezone.utc) - OUTPUT_RETENTION).isoformat()
    with database_connection() as connection:
        expired = connection.execute("SELECT id, output_path FROM jobs WHERE created_at < ?", (cutoff,)).fetchall()
        for row in expired:
            Path(row["output_path"]).unlink(missing_ok=True)
            connection.execute("DELETE FROM jobs WHERE id = ?", (row["id"],))


@app.get("/")
def index():
    current_owner_id()
    return render_template("index.html")


@app.get("/robots.txt")
def robots_txt():
    content = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /healthz

Sitemap: https://pdffree4u.com/sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap_xml():
    content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://pdffree4u.com/</loc>
  </url>
</urlset>
"""
    return Response(content, mimetype="application/xml")


@app.get("/api/history")
def history():
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT id, tool, output_name, input_bytes, output_bytes, created_at FROM jobs "
            "WHERE owner_id = ? ORDER BY created_at DESC LIMIT 8",
            (current_owner_id(),),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/pdf-preview")
def pdf_preview():
    upload = request.files.get("file")
    if upload is None:
        return jsonify(error="Choose a PDF file to preview."), 400
    try:
        _, content = read_upload(upload)
        document = fitz.open(stream=content, filetype="pdf")
        if document.needs_pass:
            document.close()
            return jsonify(error="Unlock this PDF before opening it in the editor."), 400
        if not document.page_count or document.page_count > MAX_PAGE_COUNT:
            document.close()
            return jsonify(error=f"This PDF must have between 1 and {MAX_PAGE_COUNT} pages."), 400
        try:
            page_number = int(request.form.get("page", "1"))
        except ValueError as error:
            document.close()
            raise ValueError("Choose a valid page number.") from error
        if not 1 <= page_number <= document.page_count:
            document.close()
            return jsonify(error="That page does not exist in this PDF."), 400
        page = document[page_number - 1]
        response = Response(page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False).tobytes("png"), mimetype="image/png")
        response.headers["X-PDF-Page-Count"] = str(document.page_count)
        response.headers["X-PDF-Page-Width"] = str(page.rect.width)
        response.headers["X-PDF-Page-Height"] = str(page.rect.height)
        response.headers["Cache-Control"] = "no-store"
        document.close()
        return response
    except (ValueError, fitz.FileDataError, fitz.EmptyFileError) as error:
        return jsonify(error=str(error)), 400


@app.post("/api/jobs")
def create_job():
    tool = normalize_tool(request.form.get("tool", ""))
    if tool not in ALLOWED_TOOLS:
        return jsonify(error="Choose a supported PDF tool."), 400

    output_dir = Path(app.config["OUTPUT_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    output_path = output_dir / f"{job_id}.bin"
    try:
        output_name, input_bytes = process_job(tool, request.files.getlist("files"), request.form, output_path)
    except (ValueError, fitz.FileDataError, fitz.EmptyFileError) as error:
        output_path.unlink(missing_ok=True)
        return jsonify(error=str(error)), 400
    except Exception:
        output_path.unlink(missing_ok=True)
        app.logger.exception("PDF job failed")
        return jsonify(error="This file could not be processed. Check that it is a valid, unprotected PDF."), 400

    output_bytes = output_path.stat().st_size
    created_at = datetime.now(timezone.utc).isoformat()
    with database_connection() as connection:
        connection.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, current_owner_id(), tool, output_name, str(output_path), input_bytes, output_bytes, created_at),
        )
    purge_expired_outputs()
    result = dict(
        id=job_id,
        tool=tool,
        outputName=output_name,
        inputBytes=input_bytes,
        outputBytes=output_bytes,
        downloadUrl=f"/api/jobs/{job_id}/download",
    )
    if tool == "compress":
        result["targetReductionPercent"] = int(request.form.get("target_reduction_percent", "85"))
        result["reductionPercent"] = round((input_bytes - output_bytes) * 100 / input_bytes, 1) if input_bytes else 0
        result["targetMet"] = abs(result["reductionPercent"] - result["targetReductionPercent"]) <= 2
    return jsonify(result)


@app.get("/api/jobs/<job_id>/download")
def download_job(job_id):
    with database_connection() as connection:
        row = connection.execute(
            "SELECT output_name, output_path FROM jobs WHERE id = ? AND owner_id = ?",
            (job_id, current_owner_id()),
        ).fetchone()
    if row is None or not Path(row["output_path"]).is_file():
        abort(404)
    return send_file(row["output_path"], as_attachment=True, download_name=row["output_name"])


@app.delete("/api/history/<job_id>")
def delete_job(job_id):
    with database_connection() as connection:
        row = connection.execute(
            "SELECT output_path FROM jobs WHERE id = ? AND owner_id = ?",
            (job_id, current_owner_id()),
        ).fetchone()
        if row is None:
            abort(404)
        Path(row["output_path"]).unlink(missing_ok=True)
        connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    return "", 204


@app.get("/healthz")
def health():
    return jsonify(status="ok")


@app.errorhandler(RequestEntityTooLarge)
def upload_too_large(_error):
    return jsonify(error="Uploads are limited to 100 MB total."), 413


@app.after_request
def secure_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response


initialize_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)