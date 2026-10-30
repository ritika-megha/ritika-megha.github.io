#!/usr/bin/env python3
"""Import public Behance cards and project metadata without overwriting local edits.

No private API, login, challenge bypass, or browser impersonation is used. A blocked
or changed page is an import failure; callers can still build the saved portfolio.
"""

import argparse
import copy
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

import yaml


USER_AGENT = "RitikaPortfolioSync/1.0 (+https://ritika-megha.github.io)"
GALLERY = re.compile(r"^/gallery/(\d+)(?:/[^?#]*)?/?$")
SYNC_FIELDS = ("title", "description", "category", "cover", "image_alt", "behance_url", "order")


def project_path(root, title, identity, existing_path=None):
    slug = re.sub(r"[\W_]+", "-", unicodedata.normalize("NFKC", title).casefold()).strip("-")[:100].rstrip("-") or "project"
    path = root / "_projects" / f"{slug}.md"
    if path.exists() and path != existing_path:
        path = path.with_name(f"{slug}-{identity}.md")
    if path.exists() and path != existing_path:
        raise ValueError("Project filename collision; existing files were kept")
    return path


def project_id(url):
    parsed = urlsplit(str(url or ""))
    match = GALLERY.match(parsed.path)
    if parsed.hostname not in (None, "www.behance.net", "behance.net") or not match:
        return None
    return match.group(1)


def project_url(url):
    if not project_id(url):
        raise ValueError("Not a public Behance project URL")
    return "https://www.behance.net" + urlsplit(url).path


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


class PublicPage(HTMLParser):
    """Read normal gallery anchors, image covers, metadata, and JSON script blocks."""

    def __init__(self, source, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.projects = {}
        self.meta = {}
        self.next_page = None
        self.anchor = None
        self.script = None
        self.json_documents = []
        self.cover_images = []
        self.feed(source)
        # Behance can put the picture beside an empty overlay link, rather than inside it.
        for identity, card in self.projects.items():
            if not card.get("cover_url"):
                card["cover_url"] = next((url for url in self.cover_images if f"{identity}." in urlsplit(url).path.rsplit("/", 1)[-1]), "")

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "meta":
            self.meta[attrs.get("property", attrs.get("name", "")).lower()] = attrs.get("content", "")
        elif tag == "a":
            url = urljoin(self.base, attrs.get("href", ""))
            self.anchor = {"url": url, "title": attrs.get("title", ""), "text": [], "cover_url": ""}
            if "next" in (attrs.get("rel", "") + " " + attrs.get("aria-label", "")).lower():
                self.next_page = url
        elif tag == "img":
            candidates = [attrs.get("src", ""), attrs.get("data-src", "")]
            cover = next((value for value in candidates if urlsplit(value).hostname == "mir-s3-cdn-cf.behance.net"), "")
            if cover:
                self.cover_images.append(cover)
            if self.anchor:
                self.anchor["cover_url"] = cover
                self.anchor["title"] = self.anchor["title"] or attrs.get("alt", "")
        elif tag == "script":
            self.script = []

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        elif self.anchor:
            self.anchor["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor:
            anchor = self.anchor
            self.anchor = None
            identity = project_id(anchor["url"])
            title = clean(anchor["title"] or " ".join(anchor["text"]))
            title = re.sub(r"^Link to project\s*[-–:]\s*", "", title, flags=re.I)
            if identity:
                previous = self.projects.get(identity, {})
                self.projects[identity] = {
                    "id": identity, "url": project_url(anchor["url"]),
                    "title": title or previous.get("title", ""),
                    "cover_url": anchor["cover_url"] or previous.get("cover_url", ""),
                }
            elif "next" in title.lower():
                self.next_page = anchor["url"]
        elif tag == "script" and self.script is not None:
            value = "".join(self.script).strip()
            self.script = None
            try:
                self.json_documents.append(json.loads(value))
            except (ValueError, TypeError):
                # Some public pages put their JSON in an explicit state assignment.
                for marker in ("window.__INITIAL_STATE__", "window.__APOLLO_STATE__", "window.__NEXT_DATA__"):
                    if marker in value:
                        try:
                            start = value.index("{", value.index(marker))
                            document, _ = json.JSONDecoder().raw_decode(value[start:])
                            self.json_documents.append(document)
                        except (ValueError, TypeError):
                            pass


def walk(document):
    if isinstance(document, dict):
        yield document
        for value in document.values():
            yield from walk(value)
    elif isinstance(document, list):
        for value in document:
            yield from walk(value)


def enrich_cards(page, username):
    for document in page.json_documents:
        for node in walk(document):
            url = node.get("url", "")
            if not isinstance(url, str) or not project_id(url):
                continue
            identity = project_id(url)
            owners = node.get("owners", [])
            if isinstance(owners, dict):
                owners = [owners]
            own_project = any(isinstance(owner, dict) and str(owner.get("username", "")).lower() == username.lower() for owner in owners)
            if identity not in page.projects and not own_project:
                continue
            card = page.projects.setdefault(identity, {"id": identity, "url": project_url(url)})
            card["title"] = card.get("title") or clean(node.get("name"))
            published = node.get("publishedOn", node.get("published_on"))
            if isinstance(published, (int, float)) and published > 0:
                card["published_on"] = int(published)
            covers = node.get("covers", {})
            if isinstance(covers, dict):
                card["cover_url"] = card.get("cover_url") or covers.get("808") or covers.get("404") or covers.get("original", "")
                available = covers.get("allAvailable", [])
                if isinstance(available, list):
                    available = [cover for cover in available if isinstance(cover, dict) and isinstance(cover.get("url"), str)]
                    preferred = next((cover["url"] for cover in available if cover.get("width") == 404 and cover.get("type") in ("JPG", "JPEG", "PNG")), "")
                    card["cover_url"] = card.get("cover_url") or preferred or next((cover["url"] for cover in available if cover.get("width") in (404, 808)), "")
            if isinstance(node.get("description"), str):
                card["description"] = clean(node["description"])
            fields = node.get("fields", [])
            if isinstance(fields, list):
                names = [clean(field.get("name") if isinstance(field, dict) else field) for field in fields]
                card["category"] = " / ".join(name for name in names[:2] if name)


class Fetcher:
    def __init__(self, delay=0.7):
        self.delay = delay
        self.last_request = 0

    def fetch(self, url, limit=12_000_000):
        wait = self.delay - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        self.last_request = time.monotonic()
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,image/*;q=0.9,*/*;q=0.5"})
        with urlopen(request, timeout=30) as response:
            payload = response.read(limit + 1)
            if len(payload) > limit:
                raise ValueError("Response exceeded the import size limit")
            return payload, response.headers.get_content_type()

    def page(self, url):
        payload, content_type = self.fetch(url)
        if content_type not in ("text/html", "application/xhtml+xml", "text/plain"):
            raise ValueError("Expected a public HTML page")
        return PublicPage(payload.decode("utf-8", errors="replace"), url)


def discover(fetcher, profile, max_pages, saved_html=None):
    username = urlsplit(profile).path.strip("/")
    projects = {}
    seen = set()
    url = profile
    for _ in range(max_pages):
        if not url or url in seen:
            break
        seen.add(url)
        page = PublicPage(saved_html.read_text(), profile) if saved_html else fetcher.page(url)
        enrich_cards(page, username)
        projects.update(page.projects)
        if saved_html:
            break
        following = urlsplit(page.next_page or "")
        if following.hostname not in ("www.behance.net", "behance.net") or following.path.rstrip("/") != urlsplit(profile).path.rstrip("/"):
            break
        url = page.next_page
    if not projects:
        raise ValueError("No project cards found; the page may be blocked, client-rendered, or changed. Saved projects were kept.")
    if url and len(seen) == max_pages and page.next_page:
        print("Warning: page limit reached; increase --max-pages to inspect more pages.", file=sys.stderr)
    # Publication time is authoritative; IDs and profile pinning are not a timeline.
    return sorted(projects.values(), key=lambda card: card.get("published_on", 0), reverse=True)


def read_project(path):
    text = path.read_text()
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)\Z", text, re.S)
    if not match:
        raise ValueError(f"Missing YAML front matter: {path}")
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Project front matter must be a mapping: {path}")
    return metadata, match.group(2)


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def image_extension(payload, content_type):
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return ".webp"
    raise ValueError(f"Cover is not a supported raster image ({content_type})")


def local_asset(root, value):
    if not value or not str(value).startswith("/assets/"):
        return None
    path = (root / str(value).lstrip("/")).resolve()
    return path if root.resolve() in path.parents and path.is_file() else None


def merge_metadata(existing, incoming, root, image_bytes):
    result = copy.deepcopy(existing)
    previous = existing.get("behance_import", {})
    if not isinstance(previous, dict):
        previous = {}
    for key in SYNC_FIELDS:
        # Missing fields are imported; previously imported fields refresh unless edited locally.
        value = existing.get(key)
        should_update = value in (None, "") or (key in previous and value == previous[key])
        if key == "cover" and not previous:
            local = local_asset(root, value)
            should_update = should_update or (local is not None and local.read_bytes() == image_bytes)
        elif key == "cover" and should_update and previous.get("cover_sha256"):
            local = local_asset(root, value)
            if local and hashlib.sha256(local.read_bytes()).hexdigest() != previous["cover_sha256"]:
                should_update = False
        if should_update:
            result[key] = incoming[key]
    result["behance_import"] = incoming
    return result


def sync_project(card, root, fetcher, known, order, dry_run=False, saved_directory=None, offline=False):
    identity = card["id"]
    path = known.get(identity)
    existing, body = read_project(path) if path else ({}, "")
    if existing.get("behance_sync") is False:
        return {"id": identity, "status": "skipped", "path": str(path.relative_to(root))}
    saved = saved_directory / f"{identity}.html" if saved_directory else None
    full_details = False
    if saved and saved.exists():
        page = PublicPage(saved.read_text(), card["url"])
        full_details = True
    else:
        page = PublicPage("", card["url"])
        if not offline and not getattr(fetcher, "detail_pages_blocked", False):
            try:
                page = fetcher.page(card["url"])
                full_details = True
            except HTTPError as error:
                if error.code not in (403, 429):
                    raise
                fetcher.detail_pages_blocked = True
                print(f"Warning: detail pages returned HTTP {error.code}. Using readable profile cards; existing descriptions will be kept.", file=sys.stderr)
    if full_details and not (page.meta.get("og:title") or page.meta.get("twitter:title")):
        raise ValueError("Project page has no readable public metadata; it may be blocked or changed")
    title = clean(page.meta.get("og:title") or page.meta.get("twitter:title") or card.get("title"))
    title = re.sub(r"\s*(?:::|\|)\s*Behance\s*$", "", title, flags=re.I)
    if not title:
        raise ValueError("Project has no readable title")
    if path is None:
        path = project_path(root, title, identity)
    cover_url = card.get("cover_url") or page.meta.get("og:image", "")
    image_url = urlsplit(urljoin(card["url"], cover_url))
    if image_url.scheme != "https" or image_url.hostname != "mir-s3-cdn-cf.behance.net":
        raise ValueError("No supported public Behance cover URL was found")
    image_bytes, content_type = fetcher.fetch(image_url.geturl())
    extension = image_extension(image_bytes, content_type)
    digest = hashlib.sha256(image_bytes).hexdigest()[:16]
    asset = f"/assets/images/behance/{path.stem}-{digest}{extension}"
    keywords = [clean(word) for word in page.meta.get("keywords", "").split(",") if clean(word)]
    previous = existing.get("behance_import", {})
    if not isinstance(previous, dict):
        previous = {}
    description = page.meta.get("og:description") or page.meta.get("description") or card.get("description")
    if not full_details and not description:
        description = previous.get("description") or existing.get("description", "")
    category = " / ".join(keywords[:2]) or card.get("category") or previous.get("category") or existing.get("category") or "Selected work"
    incoming = {
        "id": identity, "title": title,
        "description": clean(description)[:5000],
        "category": category,
        "cover": asset, "image_alt": f"Cover artwork for {title}.",
        "behance_url": card["url"], "cover_url": image_url.geturl(),
        "cover_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "details": "project-page" if full_details else "profile-only",
        "order": order,
        "published_on": card.get("published_on"),
    }
    metadata = merge_metadata(existing, incoming, root, image_bytes)
    if not existing:
        metadata.update({"order": order, "destination": "auto", "visible": True, "disc_artwork": ""})
    changed = metadata != existing
    if not dry_run:
        asset_path = root / asset.lstrip("/")
        if not asset_path.exists():
            atomic_write(asset_path, image_bytes)
        if changed:
            front = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True, width=1000)
            atomic_write(path, ("---\n" + front + "---\n" + body).encode())
    return {"id": identity, "status": "new" if not existing else "updated" if changed else "unchanged", "path": str(path.relative_to(root)), "details": incoming["details"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile", default="https://www.behance.net/ritikamegha")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--profile-html", type=Path, help="Import a saved public profile HTML file instead of fetching Behance pages")
    parser.add_argument("--project-html-dir", type=Path, help="Optional saved project pages named PROJECT_ID.html")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    report = {"profile": args.profile, "dry_run": args.dry_run, "projects": [], "errors": []}
    try:
        profile = urlsplit(args.profile)
        if profile.scheme != "https" or profile.hostname != "www.behance.net" or not re.fullmatch(r"/[A-Za-z0-9_-]+/?", profile.path):
            raise ValueError("Use an HTTPS www.behance.net profile URL")
        if not 1 <= args.max_pages <= 100:
            raise ValueError("--max-pages must be between 1 and 100")
        fetcher = Fetcher()
        if not args.profile_html:
            robots_bytes, _ = fetcher.fetch("https://www.behance.net/robots.txt")
            robots = RobotFileParser()
            robots.parse(robots_bytes.decode("utf-8").splitlines())
            if not robots.can_fetch(USER_AGENT, args.profile) or not robots.can_fetch(USER_AGENT, "https://www.behance.net/gallery/1/project"):
                raise ValueError("Behance robots rules do not permit this public-page import")
        known = {}
        for path in sorted((root / "_projects").glob("*.md")):
            metadata, _ = read_project(path)
            identity = project_id(metadata.get("behance_url"))
            if identity:
                if identity in known:
                    raise ValueError(f"Duplicate Behance ID {identity}; resolve the duplicate project files first")
                known[identity] = path
        cards = discover(fetcher, args.profile, args.max_pages, args.profile_html)
        print(f"Discovered {len(cards)} project(s). This does not guarantee a complete account export.")
        for rank, card in enumerate(cards, 1):
            try:
                result = sync_project(card, root, fetcher, known, rank, args.dry_run, args.project_html_dir, bool(args.profile_html))
                report["projects"].append(result)
                print(f"{result['status']}: {result['path']}")
            except (HTTPError, URLError, ValueError, OSError) as error:
                message = f"Project {card['id']}: {error}"
                report["errors"].append(message)
                print(message, file=sys.stderr)
    except (HTTPError, URLError, ValueError, OSError, yaml.YAMLError) as error:
        report["errors"].append(str(error))
        print(f"Behance import failed: {error}. Existing projects were kept.", file=sys.stderr)
    finally:
        if args.report:
            atomic_write(args.report, (json.dumps(report, indent=2) + "\n").encode())
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
