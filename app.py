import io
import os
import sqlite3
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
ALLOWED_TOOLS = {"merge", "split", "compress", "rotate", "images-to-pdf"}

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
    if not value.strip():
        return [[page_number] for page_number in range(page_count)]
    groups = []
    seen = set()
    for part in value.split(","):
        bounds = part.strip().split("-")
        if len(bounds) > 2 or not all(bound.strip().isdigit() for bound in bounds):
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
    return groups


def process_job(tool, uploads, options, output_path):
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
            raise ValueError(f"{filename} is password-protected. Unlock it before processing.")
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

    if tool == "compress":
        document = fitz.open(stream=input_files[0][1], filetype="pdf")
        document.save(output_path, garbage=4, deflate=True, clean=True)
        document.close()
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


@app.post("/api/jobs")
def create_job():
    tool = request.form.get("tool", "")
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
    return jsonify(
        id=job_id,
        tool=tool,
        outputName=output_name,
        inputBytes=input_bytes,
        outputBytes=output_bytes,
        downloadUrl=f"/api/jobs/{job_id}/download",
    )


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