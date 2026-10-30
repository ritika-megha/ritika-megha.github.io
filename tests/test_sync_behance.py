import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_behance as sync


PROFILE = "https://www.behance.net/ritikamegha"
PROJECT = "https://www.behance.net/gallery/123/Example"
IMAGE = "https://mir-s3-cdn-cf.behance.net/projects/404/example.png"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aDPkAAAAASUVORK5CYII=")
PROFILE_HTML = f'<a href="{PROJECT}"><img src="{IMAGE}" alt="Example"></a>'


def detail(title="Example", description="A graphic design project."):
    return f'<meta property="og:title" content="{title} :: Behance"><meta property="og:description" content="{description}"><meta property="og:image" content="{IMAGE}"><meta name="keywords" content="Graphic Design, Branding">'


class Fetcher:
    def __init__(self):
        self.pages = {PROFILE: PROFILE_HTML, PROJECT: detail()}
        self.image = PNG
        self.calls = []

    def page(self, url):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return sync.PublicPage(value, url)

    def fetch(self, url):
        self.calls.append(url)
        if url.endswith("robots.txt"):
            return b"User-agent: *\nAllow: /", "text/plain"
        return self.image, "image/png"


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "_projects").mkdir()
        self.fetcher = Fetcher()
        self.card = {"id": "123", "url": PROJECT, "title": "Example", "cover_url": IMAGE}
        self.path = self.root / "_projects/example.md"

    def create(self, path=None, **values):
        path = path or self.path
        path.write_text("---\n" + sync.yaml.safe_dump(values) + "---\n\nMy own **case study**.\n")
        return path

    def run_import(self, known=None, **kwargs):
        return sync.sync_project(self.card, self.root, self.fetcher, known or {}, 8, **kwargs)

    def test_html_cards_and_pagination(self):
        source = PROFILE_HTML + '<a href="?page=2" aria-label="Next page">Next</a>'
        page = sync.PublicPage(source, PROFILE)
        self.assertEqual(page.projects["123"]["title"], "Example")
        self.assertEqual(page.projects["123"]["cover_url"], IMAGE)
        self.assertEqual(page.next_page, PROFILE + "?page=2")

    def test_lazy_image_ignores_placeholder(self):
        page = sync.PublicPage(f'<a href="{PROJECT}"><img src="data:image/png;base64,placeholder" data-src="{IMAGE}" alt="Example"></a>', PROFILE)
        self.assertEqual(page.projects["123"]["cover_url"], IMAGE)

    def test_sibling_picture_and_overlay_link(self):
        cover = "https://mir-s3-cdn-cf.behance.net/projects/404/abc123.png"
        page = sync.PublicPage(f'<picture><img src="{cover}" alt="Example"></picture><a href="{PROJECT}" title="Link to project - Example"></a>', PROFILE)
        self.assertEqual(page.projects["123"]["cover_url"], cover)
        self.assertEqual(page.projects["123"]["title"], "Example")

    def test_all_available_cover_schema(self):
        data = {"url": PROJECT, "name": "Example", "owners": [{"username": "ritikamegha"}], "covers": {"allAvailable": [{"url": IMAGE, "width": 404, "type": "PNG"}]}}
        page = sync.PublicPage('<script type="application/json">' + json.dumps(data) + '</script>', PROFILE)
        sync.enrich_cards(page, "ritikamegha")
        self.assertEqual(page.projects["123"]["cover_url"], IMAGE)

    def test_json_owner_filter(self):
        records = [{"url": PROJECT, "name": "Example", "covers": {"808": IMAGE}, "owners": [{"username": "ritikamegha"}]}, {"url": "https://www.behance.net/gallery/999/Other", "name": "Other", "owners": [{"username": "someoneelse"}]}]
        page = sync.PublicPage('<script type="application/ld+json">' + json.dumps(records) + '</script>', PROFILE)
        sync.enrich_cards(page, "ritikamegha")
        self.assertEqual(list(page.projects), ["123"])

    def test_pagination_deduplicates_and_stops(self):
        self.fetcher.pages[PROFILE] += '<a href="?page=2" rel="next">Next</a>'
        self.fetcher.pages[PROFILE + "?page=2"] = PROFILE_HTML + f'<a href="{PROFILE}" rel="next">Next</a>'
        self.assertEqual(len(sync.discover(self.fetcher, PROFILE, 10)), 1)
        self.assertEqual(len(self.fetcher.calls), 2)

    def test_new_project_and_no_duplicate_on_refresh(self):
        self.assertEqual(self.run_import()["status"], "new")
        metadata, _ = sync.read_project(self.path)
        self.assertEqual(metadata["title"], "Example")
        self.assertEqual(metadata["order"], 8)
        self.assertTrue((self.root / metadata["cover"].lstrip("/")).exists())
        self.assertTrue(Path(metadata["cover"]).name.startswith('example-'))
        self.assertEqual(self.run_import({"123": self.path})["status"], "unchanged")
        self.assertEqual(len(list((self.root / "_projects").glob("*.md"))), 1)

    def test_remote_refresh_updates_owned_fields(self):
        self.run_import()
        self.fetcher.pages[PROJECT] = detail("Updated", "New description")
        self.fetcher.image += b"new-cover"
        self.run_import({"123": self.path})
        metadata, _ = sync.read_project(self.path)
        self.assertEqual(metadata["title"], "Updated")
        self.assertEqual(metadata["description"], "New description")
        self.assertEqual(len(list((self.root / "assets/images/behance").glob("*.png"))), 2)

    def test_manual_fields_and_body_survive_refresh(self):
        self.run_import()
        metadata, _ = sync.read_project(self.path)
        metadata.update({"title": "My edited title", "category": "Motion", "order": 2, "destination": "internal", "visible": False, "published": False, "disc_artwork": "/assets/my-disc.png", "focal_point": "70% 40%"})
        self.create(**metadata)
        before_body = sync.read_project(self.path)[1]
        self.fetcher.pages[PROJECT] = detail("Remote change", "New source description")
        self.run_import({"123": self.path})
        updated, body = sync.read_project(self.path)
        for key in ("title", "category", "order", "destination", "visible", "published", "disc_artwork", "focal_point"):
            self.assertEqual(updated[key], metadata[key])
        self.assertEqual(body, before_body)
        self.assertEqual(updated["description"], "New source description")
        self.assertEqual(updated["behance_import"]["title"], "Remote change")

    def test_adopting_existing_record_preserves_curated_title(self):
        path = self.create(self.root / "_projects/curated.md", title="Curated title", category="Graphics", behance_url=PROJECT, order=1)
        self.run_import({"123": path})
        metadata, body = sync.read_project(path)
        self.assertEqual(metadata["title"], "Curated title")
        self.assertEqual(metadata["category"], "Graphics")
        self.assertIn("My own **case study**.", body)
        self.assertFalse(self.path.exists())

    def test_matching_old_thumbnail_is_adopted(self):
        cover = self.root / "assets/old.png"
        cover.parent.mkdir()
        cover.write_bytes(PNG)
        self.create(title="Old", cover="/assets/old.png", behance_url=PROJECT)
        self.run_import({"123": self.path})
        self.assertTrue(sync.read_project(self.path)[0]["cover"].startswith("/assets/images/behance/"))

    def test_custom_cover_is_preserved(self):
        cover = self.root / "assets/custom.png"
        cover.parent.mkdir()
        cover.write_bytes(PNG + b"custom")
        self.create(title="Old", cover="/assets/custom.png", behance_url=PROJECT)
        self.run_import({"123": self.path})
        self.assertEqual(sync.read_project(self.path)[0]["cover"], "/assets/custom.png")
        self.assertEqual(cover.read_bytes(), PNG + b"custom")

    def test_locally_replaced_imported_image_is_preserved(self):
        self.run_import()
        metadata, _ = sync.read_project(self.path)
        cover = self.root / metadata["cover"].lstrip("/")
        cover.write_bytes(PNG + b"local-edit")
        self.fetcher.image += b"remote-edit"
        self.run_import({"123": self.path})
        self.assertEqual(sync.read_project(self.path)[0]["cover"], metadata["cover"])
        self.assertEqual(cover.read_bytes(), PNG + b"local-edit")

    def test_opt_out_does_not_fetch(self):
        self.create(title="Opt out", behance_url=PROJECT, behance_sync=False)
        before = self.path.read_bytes()
        self.assertEqual(self.run_import({"123": self.path})["status"], "skipped")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.fetcher.calls, [])

    def test_failed_asset_preserves_existing_record(self):
        self.create(title="Existing", behance_url=PROJECT)
        before = self.path.read_bytes()
        self.fetcher.image = b"<html>Blocked</html>"
        with self.assertRaises(ValueError):
            self.run_import({"123": self.path})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.root / "assets").exists())

    def test_blocked_project_metadata_is_not_imported(self):
        self.fetcher.pages[PROJECT] = "<html>Access denied</html>"
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertFalse(self.path.exists())

    def test_forbidden_details_fall_back_to_public_profile_card(self):
        self.fetcher.pages[PROJECT] = HTTPError(PROJECT, 403, "Forbidden", {}, None)
        self.run_import()
        metadata, _ = sync.read_project(self.path)
        self.assertEqual(metadata["title"], "Example")
        self.assertEqual(metadata["behance_import"]["details"], "profile-only")
        self.assertTrue(self.fetcher.detail_pages_blocked)

    def test_profile_fallback_keeps_description_and_stops_detail_requests(self):
        self.run_import()
        self.fetcher.calls = []
        self.fetcher.detail_pages_blocked = True
        self.run_import({"123": self.path})
        metadata, _ = sync.read_project(self.path)
        self.assertEqual(metadata["description"], "A graphic design project.")
        self.assertNotIn(PROJECT, self.fetcher.calls)

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.run_import(dry_run=True)["status"], "new")
        self.assertFalse(self.path.exists())
        self.assertFalse((self.root / "assets").exists())

    def test_filename_collision_does_not_adopt_custom_page(self):
        self.create(title="Custom page without Behance")
        self.create(self.root / "_projects/example-123.md", title="Another custom page")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertEqual(self.path.read_bytes(), before)

    def test_network_failure_keeps_custom_pages(self):
        custom = self.create(self.root / "_projects/custom.md", title="My page")
        before = custom.read_bytes()
        self.fetcher.pages[PROFILE] = URLError("Blocked")
        report = self.root / "report.json"
        with patch.object(sync, "Fetcher", return_value=self.fetcher):
            self.assertEqual(sync.main(["--root", str(self.root), "--report", str(report)]), 1)
        self.assertEqual(custom.read_bytes(), before)
        self.assertTrue(json.loads(report.read_text())["errors"])

    def test_partial_failure_retains_success_and_reports_error(self):
        second = "https://www.behance.net/gallery/456/Blocked"
        self.fetcher.pages[PROFILE] += f'<a href="{second}">Blocked</a>'
        self.fetcher.pages[second] = URLError("Unavailable")
        report = self.root / "report.json"
        with patch.object(sync, "Fetcher", return_value=self.fetcher):
            self.assertEqual(sync.main(["--root", str(self.root), "--report", str(report)]), 1)
        self.assertTrue(self.path.exists())
        self.assertFalse((self.root / "_projects/blocked.md").exists())
        self.assertEqual(len(json.loads(report.read_text())["projects"]), 1)

    def test_duplicate_ids_fail_without_writes(self):
        self.create(title="One", behance_url=PROJECT)
        other = self.create(self.root / "_projects/duplicate.md", title="Two", behance_url=PROJECT)
        before = other.read_bytes()
        with patch.object(sync, "Fetcher", return_value=self.fetcher):
            self.assertEqual(sync.main(["--root", str(self.root)]), 1)
        self.assertEqual(other.read_bytes(), before)
        self.assertFalse((self.root / "assets").exists())

    def test_title_based_filename_collision_gets_id_suffix(self):
        self.create(title="A custom page")
        self.run_import()
        self.assertTrue((self.root / "_projects/example-123.md").exists())
        self.assertEqual(sync.read_project(self.path)[0]["title"], "A custom page")

    def test_unicode_project_filename(self):
        self.assertEqual(sync.project_path(self.root, "تاج محل", "123").name, "تاج-محل.md")

    def test_publication_date_overrides_profile_pinning(self):
        nodes = [{"url": PROJECT, "name": "Pinned older project", "publishedOn": 100}, {"url": "https://www.behance.net/gallery/456/Newer", "name": "Newer", "publishedOn": 200}]
        self.fetcher.pages[PROFILE] = PROFILE_HTML + '<a href="https://www.behance.net/gallery/456/Newer">Newer</a><script type="application/json">' + json.dumps(nodes) + '</script>'
        cards = sync.discover(self.fetcher, PROFILE, 10)
        self.assertEqual([card["id"] for card in cards], ["456", "123"])

    def test_timeline_rank_updates_unedited_order(self):
        self.run_import()
        sync.sync_project(self.card, self.root, self.fetcher, {"123": self.path}, 2)
        self.assertEqual(sync.read_project(self.path)[0]["order"], 2)


if __name__ == "__main__":
    unittest.main()
