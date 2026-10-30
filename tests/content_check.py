"""Check generated links plus internal pages, artwork overrides, and hidden work.

Run after building the main site. Test content is created only in a temporary
copy of the source, so the owner's project files remain untouched.
"""

import shutil
import re
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.tags = []
        self.feed(path.read_text())

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))


def validate_links(output, baseurl=""):
    count = 0
    for file in output.rglob("*.html"):
        for tag, attributes in Page(file).tags:
            for key in ("href", "src"):
                value = attributes.get(key)
                if not value or value.startswith("#"):
                    continue
                url = urlsplit(value)
                if url.scheme or url.netloc:
                    continue
                path = unquote(url.path)
                if baseurl and path.startswith(baseurl + "/"):
                    path = path[len(baseurl):]
                target = output / path.lstrip("/") if path.startswith("/") else file.parent / path
                if target.is_dir():
                    target /= "index.html"
                assert target.exists(), f"Broken {key} in {file}: {value}"
                count += 1
            if tag == "img":
                assert attributes.get("alt"), f"Missing image description in {file}"
    return count


assert (ROOT / "_site/index.html").exists(), "Build the main site first."
main_links = validate_links(ROOT / "_site")
main_page = Page(ROOT / "_site/index.html")
main_count = sum(tag == 'a' and attrs.get('class') == 'disc' for tag, attrs in main_page.tags)
main_images = [attrs for tag, attrs in main_page.tags if tag == 'img']
main_discs = [attrs for tag, attrs in main_page.tags if tag == 'a' and attrs.get('class') == 'disc']
main_covers = {disc['href']: image['src'] for disc, image in zip(main_discs, main_images)}
social_urls = {attrs.get('href') for tag, attrs in main_page.tags if tag == 'a'}
assert {'https://www.linkedin.com/in/ritikamegha/', 'mailto:ritikamegha.vocation@gmail.com', 'https://x.com/ritika_megha'} <= social_urls
with tempfile.TemporaryDirectory(prefix="portfolio-content-") as directory:
    source = Path(directory).resolve()
    for name in ("_layouts", "_includes", "_plugins", "_projects", "assets"):
        shutil.copytree(ROOT / name, source / name)
    for name in ("_config.yml", "index.html"):
        shutil.copy2(ROOT / name, source / name)

    project = source / "_projects/sculpture-murti.md"
    text = re.sub(r'(?m)^disc_artwork:.*$', 'disc_artwork: /assets/images/projects/tiffany.png\ndestination: internal', project.read_text())
    text = re.sub(r'(?m)^collection:.*$', 'collection: "Textiles & Graphics"', text)
    text = re.sub(r'(?m)^order:.*$', 'order: 0', text)
    project.write_text(text + "\n## Process notes\n\nAn internal case-study test fixture.\n")
    hidden = source / "_projects/vacation-vibe.md"
    hidden.write_text(re.sub(r'(?m)^order:.*$', 'visible: false\npublished: false\norder: 5', hidden.read_text()))
    for index, behance_field in enumerate(("", 'behance_url: ""\n', 'behance_url: "   "\ndestination: external\n')):
        custom = source / f"_projects/custom-{index}.md"
        custom.write_text('---\ntitle: "Custom project"\ncategory: Graphics\norder: 999\ncover: /assets/images/projects/weave.jpg\nimage_alt: Woven sample\n' + behance_field + '---\n\nCustom page body.\n')

    subprocess.run([
        str(ROOT / "bin/bundle"), "exec", "ruby", "-e",
        "Dir.chdir(ARGV.shift) { load Gem.bin_path('jekyll', 'jekyll') }", str(source),
        "build", "--strict_front_matter",
        "--source", str(source), "--config", str(source / "_config.yml"),
        "--destination", str(source / "_site"), "--baseurl", "/portfolio-check",
    ], check=True)
    output = source / "_site"
    page = Page(output / "index.html")
    discs = [attributes for tag, attributes in page.tags if tag == "a" and attributes.get("class") == "disc"]
    assert len(discs) == main_count - 1 + 3, "Hidden project or custom page visibility failed."
    assert discs[0]["href"] == "/portfolio-check/work/sculpture/", "Internal destination or preserved permalink is wrong."
    assert "target" not in discs[0], "Internal project should stay in the same tab."
    assert discs[0]['data-collection'] == 'Textiles & Graphics', 'Collection front matter was shadowed by Jekyll.'
    collection_row = next(attrs for tag, attrs in page.tags if attrs.get('id') == 'project-collection-row')
    assert 'hidden' not in collection_row, 'Configured Collection row should be visible.'
    images = [attributes for tag, attributes in page.tags if tag == "img"]
    assert images[0]["src"] == "/portfolio-check/assets/images/projects/tiffany.png", "Custom artwork override failed."
    original_href = discs[1]['href'].removeprefix('/portfolio-check')
    assert images[1]["src"] == "/portfolio-check" + main_covers[original_href], "Thumbnail default failed."
    assert "An internal case-study test fixture." in (output / "work/sculpture/index.html").read_text()
    assert not (output / "work/vacation-vibe/index.html").exists(), "Unpublished project generated a public page."
    for index in range(3):
        url = f'/portfolio-check/work/custom-{index}/'
        card = next(disc for disc in discs if disc['href'] == url)
        assert card['data-destination'] == 'internal' and 'target' not in card
        body = (output / f'work/custom-{index}/index.html').read_text()
        assert 'Custom page body.' in body and 'View on Behance' not in body
    fixture_links = validate_links(output, "/portfolio-check")
    print(f"Content checks passed: {main_links + fixture_links} local links/assets, socials, internal Markdown, missing/empty/whitespace Behance URLs, artwork override, thumbnail fallback, hidden project, and subpath deployment.")
