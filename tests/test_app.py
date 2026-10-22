import base64
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app, initialize_database


class PdfStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        app.config.update(
            TESTING=True,
            DATABASE_PATH=str(root / "jobs.sqlite3"),
            OUTPUT_DIR=str(root / "outputs"),
        )
        initialize_database()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def pdf_bytes(page_count=1):
        writer = PdfWriter()
        for _ in range(page_count):
            writer.add_blank_page(width=612, height=792)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def submit_pdf(self, tool, page_count=1, **options):
        data = {"tool": tool, **options, "files": (io.BytesIO(self.pdf_bytes(page_count)), "source.pdf")}
        return self.client.post("/api/jobs", data=data, content_type="multipart/form-data")

    def test_merge_creates_valid_two_page_pdf_and_history(self):
        data = {
            "tool": "merge",
            "files": [
                (io.BytesIO(self.pdf_bytes(1)), "first.pdf"),
                (io.BytesIO(self.pdf_bytes(2)), "second.pdf"),
            ],
        }
        response = self.client.post("/api/jobs", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.json)
        with self.client.get(response.json["downloadUrl"]) as download:
            self.assertEqual(len(PdfReader(io.BytesIO(download.data)).pages), 3)
        self.assertEqual(len(self.client.get("/api/history").json), 1)

    def test_split_saves_requested_ranges_in_zip(self):
        response = self.submit_pdf("split", page_count=3, ranges="1-2,3")
        self.assertEqual(response.status_code, 200, response.json)
        with self.client.get(response.json["downloadUrl"]) as download:
            with zipfile.ZipFile(io.BytesIO(download.data)) as archive:
                self.assertEqual(archive.namelist(), ["pages_01.pdf", "pages_02.pdf"])
                self.assertEqual(len(PdfReader(io.BytesIO(archive.read("pages_01.pdf"))).pages), 2)

    def test_remove_pdf_pages_preserves_unselected_pages_and_rejects_removing_all(self):
        document = fitz.open()
        for label in ("Page one", "Page two", "Page three"):
            page = document.new_page(width=612, height=792)
            page.insert_text((72, 90), label, fontsize=18)
        source = document.tobytes()
        document.close()

        response = self.client.post(
            "/api/jobs",
            data={
                "tool": "remove-pages",
                "ranges": "2",
                "files": (io.BytesIO(source), "source.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        with self.client.get(response.json["downloadUrl"]) as download:
            result = fitz.open(stream=download.data, filetype="pdf")
            self.assertEqual(result.page_count, 2)
            self.assertIn("Page one", result[0].get_text())
            self.assertIn("Page three", result[1].get_text())
            result.close()

        remove_all = self.client.post(
            "/api/jobs",
            data={
                "tool": "remove-pages",
                "ranges": "1-3",
                "files": (io.BytesIO(source), "source.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(remove_all.status_code, 400)
        self.assertIn("Keep at least one page", remove_all.json["error"])

    def test_compress_and_rotate_return_readable_pdfs(self):
        compressed = self.submit_pdf("compress")
        self.assertEqual(compressed.status_code, 200, compressed.json)
        with self.client.get(compressed.json["downloadUrl"]) as compressed_file:
            self.assertEqual(len(PdfReader(io.BytesIO(compressed_file.data)).pages), 1)

        rotated = self.submit_pdf("rotate", degrees="90")
        self.assertEqual(rotated.status_code, 200, rotated.json)
        with self.client.get(rotated.json["downloadUrl"]) as rotated_file:
            self.assertEqual(PdfReader(io.BytesIO(rotated_file.data)).pages[0].rotation, 90)

    def test_compression_target_changes_output_and_reports_actual_size(self):
        image_bytes = io.BytesIO()
        Image.effect_noise((900, 900), 100).convert("RGB").save(image_bytes, format="JPEG", quality=95)
        document = fitz.open()
        page = document.new_page(width=612, height=792)
        page.insert_image(page.rect, stream=image_bytes.getvalue())
        source = document.tobytes()
        document.close()

        responses = []
        for target in (30, 70, 85):
            response = self.client.post(
                "/api/jobs",
                data={
                    "tool": "compress",
                    "target_reduction_percent": str(target),
                    "files": (io.BytesIO(source), "image-heavy.pdf"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200, response.json)
            with self.client.get(response.json["downloadUrl"]) as download:
                self.assertEqual(response.json["outputBytes"], len(download.data))
            responses.append(response.json)

        self.assertEqual(responses[0]["targetReductionPercent"], 30)
        self.assertEqual(responses[1]["targetReductionPercent"], 70)
        self.assertEqual(responses[2]["targetReductionPercent"], 85)
        self.assertEqual(responses[2]["inputBytes"], len(source))
        self.assertGreater(responses[2]["reductionPercent"], 0)
        for result, target in zip(responses, (30, 70, 85)):
            self.assertTrue(result["targetMet"])
            self.assertLessEqual(abs(result["reductionPercent"] - target), 2)
        self.assertLess(responses[1]["outputBytes"], responses[0]["outputBytes"])

    def test_compression_reports_unreachable_target_for_vector_pdf(self):
        document = fitz.open()
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 90), "Vector-only document", fontsize=22)
        source = document.tobytes()
        document.close()

        response = self.client.post(
            "/api/jobs",
            data={
                "tool": "compress",
                "target_reduction_percent": "90",
                "files": (io.BytesIO(source), "vector.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["targetReductionPercent"], 90)
        self.assertFalse(response.json["targetMet"])
        with self.client.get(response.json["downloadUrl"]) as download:
            self.assertEqual(response.json["outputBytes"], len(download.data))

    def test_images_convert_to_pdf(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (20, 30), "#d46c52").save(image_bytes, format="PNG")
        response = self.client.post(
            "/api/jobs",
            data={"tool": "images-to-pdf", "files": (io.BytesIO(image_bytes.getvalue()), "scan.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        with self.client.get(response.json["downloadUrl"]) as result:
            self.assertEqual(len(PdfReader(io.BytesIO(result.data)).pages), 1)

    def test_edit_pdf_adds_text_to_selected_page(self):
        document = fitz.open()
        document.new_page(width=612, height=792)
        document.new_page(width=612, height=792)
        source = document.tobytes()
        document.close()

        response = self.client.post(
            "/api/jobs",
            data={
                "tool": "edit-pdf",
                "edit_mode": "add",
                "edit_text": "Approved copy",
                "edit_pages": "2",
                "edit_position": "top-left",
                "edit_font_size": "18",
                "files": (io.BytesIO(source), "source.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        with self.client.get(response.json["downloadUrl"]) as download:
            edited = fitz.open(stream=download.data, filetype="pdf")
            self.assertNotIn("Approved copy", edited[0].get_text())
            self.assertIn("Approved copy", edited[1].get_text())
            edited.close()

    def test_edit_pdf_replaces_existing_text(self):
        document = fitz.open()
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 100), "Draft heading", fontsize=18)
        source = document.tobytes()
        document.close()

        response = self.client.post(
            "/api/jobs",
            data={
                "tool": "edit-pdf",
                "edit_mode": "replace",
                "edit_find_text": "Draft heading",
                "edit_replacement_text": "Final heading",
                "files": (io.BytesIO(source), "source.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        with self.client.get(response.json["downloadUrl"]) as download:
            edited = fitz.open(stream=download.data, filetype="pdf")
            text = edited[0].get_text()
            self.assertNotIn("Draft heading", text)
            self.assertIn("Final heading", text)
            edited.close()

    def test_pdf_preview_renders_requested_page(self):
        response = self.client.post(
            "/api/pdf-preview",
            data={"file": (io.BytesIO(self.pdf_bytes(2)), "source.pdf"), "page": "2"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.headers["X-PDF-Page-Count"], "2")
        self.assertGreater(len(response.data), 100)

    def test_edit_pdf_applies_canvas_annotations_to_selected_page(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (24, 24), "#2266cc").save(image_bytes, format="PNG")
        operations = [
            {
                "type": "text",
                "page": 1,
                "x": 0.12,
                "y": 0.14,
                "text": "Canvas note",
                "font_size": 18,
                "color": "#18345b",
            },
            {"type": "rectangle", "page": 1, "x": 0.1, "y": 0.3, "x2": 0.6, "y2": 0.55, "color": "#e55353"},
            {
                "type": "image",
                "page": 1,
                "x": 0.65,
                "y": 0.3,
                "x2": 0.85,
                "y2": 0.5,
                "data": f"data:image/png;base64,{base64.b64encode(image_bytes.getvalue()).decode('ascii')}",
            },
        ]
        response = self.client.post(
            "/api/jobs",
            data={
                "tool": "edit-pdf",
                "edit_operations": json.dumps(operations),
                "files": (io.BytesIO(self.pdf_bytes(2)), "source.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        with self.client.get(response.json["downloadUrl"]) as download:
            edited = fitz.open(stream=download.data, filetype="pdf")
            self.assertEqual(edited.page_count, 2)
            self.assertNotIn("Canvas note", edited[0].get_text())
            self.assertIn("Canvas note", edited[1].get_text())
            self.assertGreater(len(edited[1].get_drawings()), 0)
            self.assertGreater(len(edited[1].get_images()), 0)
            edited.close()

    def test_sign_pdf_applies_drawn_signature_to_selected_page(self):
        operations = [
            {
                "type": "signature",
                "page": 1,
                "x": 0.15,
                "y": 0.55,
                "x2": 0.62,
                "y2": 0.72,
                "points": [[0.15, 0.55], [0.24, 0.48], [0.31, 0.66], [0.42, 0.51], [0.62, 0.72]],
                "color": "#18345b",
                "width": 3,
            }
        ]
        response = self.client.post(
            "/api/jobs",
            data={
                "tool": "sign-pdf",
                "edit_operations": json.dumps(operations),
                "files": (io.BytesIO(self.pdf_bytes(2)), "source.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["outputName"], "signed.pdf")
        with self.client.get(response.json["downloadUrl"]) as download:
            signed = fitz.open(stream=download.data, filetype="pdf")
            self.assertEqual(signed.page_count, 2)
            self.assertEqual(len(signed[0].get_drawings()), 0)
            self.assertGreater(len(signed[1].get_drawings()), 0)
            signed.close()

    def test_protect_and_unlock_pdf_round_trip(self):
        response = self.client.post(
            "/api/jobs",
            data={"tool": "protect", "password": "secret123", "files": (io.BytesIO(self.pdf_bytes(2)), "source.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.json)
        unlocked = self.client.post(
            "/api/jobs",
            data={"tool": "unlock", "password": "secret123", "files": (io.BytesIO(self.client.get(response.json["downloadUrl"]).data), "protected.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(unlocked.status_code, 200, unlocked.json)

    def test_all_feature_tools_are_registered(self):
        expected = {
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
        }
        self.assertTrue(expected.issubset(__import__("app").ALLOWED_TOOLS))

    def test_rejects_bad_ranges_and_hides_downloads_from_other_sessions(self):
        invalid = self.submit_pdf("split", page_count=2, ranges="1-4")
        self.assertEqual(invalid.status_code, 400)

        created = self.submit_pdf("compress")
        other_client = app.test_client()
        self.assertEqual(other_client.get(created.json["downloadUrl"]).status_code, 404)

    def test_health_endpoint(self):
        self.assertEqual(self.client.get("/healthz").json, {"status": "ok"})

    def test_search_engine_routes(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("Sitemap: https://pdffree4u.com/sitemap.xml", robots.get_data(as_text=True))
        self.assertIn("Disallow: /api/", robots.get_data(as_text=True))

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        root = ET.fromstring(sitemap.data)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        location = root.find("sm:url/sm:loc", namespace)
        self.assertIsNotNone(location)
        self.assertEqual(location.text, "https://pdffree4u.com/")


if __name__ == "__main__":
    unittest.main()