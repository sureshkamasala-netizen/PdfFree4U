import io
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

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

    def test_compress_and_rotate_return_readable_pdfs(self):
        compressed = self.submit_pdf("compress")
        self.assertEqual(compressed.status_code, 200, compressed.json)
        with self.client.get(compressed.json["downloadUrl"]) as compressed_file:
            self.assertEqual(len(PdfReader(io.BytesIO(compressed_file.data)).pages), 1)

        rotated = self.submit_pdf("rotate", degrees="90")
        self.assertEqual(rotated.status_code, 200, rotated.json)
        with self.client.get(rotated.json["downloadUrl"]) as rotated_file:
            self.assertEqual(PdfReader(io.BytesIO(rotated_file.data)).pages[0].rotation, 90)

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