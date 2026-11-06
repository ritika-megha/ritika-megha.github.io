# Ritika Megha — portfolio

A Jekyll portfolio inspired by a collection of CDs. Drag, swipe, scroll, use the arrow keys/buttons, or click a neighboring disc to center it. Click the centered disc or **View project** to open the work. **Index** provides direct links to every project.

## Inspiration and credit

The CD carousel concept and interaction direction are inspired by [Ravi Klaassens](https://raviklaassens.com/) and his [A24 — Films experiment](https://a24.raviklaassens.com/). Credit for the original reference design belongs to Ravi. This portfolio uses Ritika Megha's project content and its own implementation; it is not affiliated with Ravi Klaassens or A24.

## Edit with Pages CMS

The repository includes `.pages.yml` for the free hosted editor at [app.pagescms.org](https://app.pagescms.org/).

To connect the editor to this repository:

1. Sign in to Pages CMS with the GitHub account that owns the repository.
2. Install its GitHub App for this repository, then open the `main` branch.
3. Use **Portfolio projects** to edit titles, Discipline, Collection, images, order, destinations, visibility, and case-study content.
4. Use **About and social links** for the bio, description, and contact links.
5. Save your changes. They are committed to GitHub and the Pages workflow rebuilds the website.

The **Refresh from Behance** action starts the import-and-deploy workflow. It is available after GitHub Actions and the Pages CMS App's required workflow permissions are enabled. You can also run the same workflow directly from GitHub Actions.

Merge mode is enabled so edits preserve importer snapshots, explicit permalinks, and technical Jekyll settings that are not shown as form fields. Existing filenames stay stable when editing titles. Preview images and custom artwork can be uploaded through the media picker. To unpublish a project completely, turn off both **Show in carousel and index** and **Publish project page**.

### Add images within a custom page

Open **Portfolio projects**, choose your project, set **Open project in** to **My own case-study page**, and scroll down to **Case study**. In **Editor** mode, place the cursor where the image belongs and use the image button to upload a file or select one from **Project images**. Add descriptive alternative text, then save the project. Images can be placed between paragraphs; they are separate from the cover and CD artwork.

New content images default to `assets/images/content/`. If using **Source** mode, an image can also be inserted as `![Description of the image](/assets/images/content/your-image.jpg)` after uploading it through the media library. Reload Pages CMS after a configuration update so the editor picks up the image settings.

`PORTFOLIO_PLAN.md` is local planning context, excluded from both Git and the published website.

## Local preview

With Ruby installed (including the Ruby supplied on this Mac):

```sh
./bin/setup
./bin/preview
```

Open http://127.0.0.1:4000. Stop the server with Control-C.

Setup installs Bundler and site dependencies inside the ignored `vendor/` folder, without changing the system Ruby installation. After initial setup, only `./bin/preview` is needed. With an existing modern Ruby/Bundler setup, standard `bundle install` and `bundle exec jekyll serve` also work.

This first build uses Jekyll 3.10 for compatibility with the Ruby supplied on this Mac and GitHub Pages. The deployment workflow uses Ruby 3.3. There is no Node or frontend build step.

## Add or edit a project

1. Upload your Behance thumbnail to `assets/images/projects/` using a short filename without spaces.
2. Copy [the project template](docs/PROJECT_TEMPLATE.md) into `_projects/your-project.md`. In GitHub's web interface, use **Add file → Create new file** and paste the template.
3. Edit the title, category, image path/description, Behance project URL, and order. Save the file.

The same project file feeds the carousel, index, and generated internal page. Projects are sorted by `order`. Behance projects initially follow publication time, newest first, rather than the profile's potentially pinned display order. The source timestamp and timeline rank are saved in `behance_import`. Saved projects without a readable date were placed after dated work; custom pages retain their manual order. Categories and shortened display titles are editable.

### Optional Collection label

To show a Collection row for a project, add `collection: "Your collection"` to its top-level YAML. Leave it empty or omit it to hide that row. This field is maintained locally and is preserved during Behance syncs. A small Jekyll build hook reads the front-matter value without conflicting with Jekyll's own collection grouping. The prepared GitHub Actions build supports this hook; build without `--safe`. The older `collection_name` field remains supported as a fallback.

### Optional custom CD artwork

Upload your artwork, then set `disc_artwork` to its local path. Leave it as `""` to use the Behance thumbnail stored in `cover`. Use a square image; the site supplies the circular mask, rim, and center hole. `focal_point`, such as `"65% 50%"`, adjusts the crop position of rectangular covers. Artwork should be reviewed with the CD hole in mind.

Generated Behance covers use the project filename followed by a content hash, for example `virupan-gopalpur-cluster-9fcc0d5b2b155e76.jpg`. The project name makes assets recognizable; the hash makes changed artwork load reliably without stale browser caches. The importer follows this convention automatically. Existing image references and import snapshots have been updated to the renamed files.

### Appearance

The header's **Auto / Light / Dark** selector is available on the homepage and internal pages. Auto follows the device's color scheme and reacts to changes. An explicit choice is remembered in this browser across reloads and page navigation. If browser storage is unavailable, the choice still applies to the current page. The default is Auto; artwork colors are preserved in all modes. Small navigation, metadata, caption, social, and counter text uses stronger weight and contrast.

### Internal case studies

Write Markdown below the second `---` line. Its page is generated at `/work/your-project/`. **Without a Behance URL (including an empty field), the carousel and index automatically open this internal page.** With a Behance URL, they open Behance instead. Set `destination: internal` to use the internal page even when a Behance URL is present. `destination: auto` is the default. The same thumbnail remains on the carousel in either case. External projects also have a basic generated page, but the carousel and index link directly to Behance.

To hide a work and prevent its generated page from publishing, set **both** `visible: false` and `published: false`. Hiding work is not access control; do not put confidential material in a public repository.

## GitHub Pages

Repository: [ritika-megha/ritika-megha.github.io](https://github.com/ritika-megha/ritika-megha.github.io). The source is on `main`, and GitHub Pages is configured to deploy through the included Actions workflow. The site address is https://ritika-megha.github.io/.

Pages is already set to **GitHub Actions**. Saving content through Pages CMS or pushing source changes to `main` starts the build and deployment. Pull requests build without deploying. You can also start the workflow manually from the repository's **Actions** tab.

For a project repository rather than an account-level site, set `baseurl` to `/repository-name` and update `url`. The templates and asset references support this prefix. Markdown body image links should include the prefix or use Liquid's `relative_url` filter.

## Content and import status

The initial six covers were downloaded from the owner's public Behance profile. The first live import subsequently saved 18 Behance projects and their covers, preserving the custom `testpage.md` and curated project fields. Imported source URLs are recorded in each project's `behance_import` metadata; see also [initial asset sources](docs/ASSET_SOURCES.md).

The public-page importer is `scripts/sync_behance.py`. On pushes to `main`, and manually triggered deployment runs with **sync_behance** checked, the workflow attempts to fetch project cards, follow explicit pagination, fetch project titles/descriptions/categories, and download cover assets. A successful import is built, committed back to `main`, and deployed in the same workflow. The bot commit does not trigger another run. Normal pull-request builds do not fetch Behance or write content.

To refresh after publishing work on Behance: **GitHub → Actions → Build and deploy portfolio → Run workflow → main → leave sync_behance checked → Run workflow.** No website code change is required. To publish saved content without a fetch, uncheck that option.

Import failures produce a warning and the saved site still builds. Partial imports keep successfully processed projects. A build failure prevents committing or deploying the imported changes. Workflow repository write permission is needed to save imports; protected branches may require a different contribution workflow before enabling bot commits.

**Live verification and limits:** a live dry run successfully discovered 18 projects across the public profile pages and fetched their cover assets. Individual project pages returned HTTP 403, so the importer falls back to readable profile cards for titles/covers and any public profile metadata. Existing descriptions are retained if the detail pages are blocked; new descriptions may be empty and categories may use `Selected work`. The workflow summary reports when profile-only metadata was used. After a 403 or 429, further detail-page requests are skipped for that run. The script does not bypass access controls or use an undocumented API. Behance blocking, client-only content, or markup changes can still prevent syncing. Explicit pagination is followed up to 10 pages; this is not a guaranteed full account export. Full case-study images, videos, and body layouts are not mirrored. The GitHub-hosted workflow has completed its first successful Behance sync, build, and deployment.

The actual local import has also completed successfully for those 18 projects; they are now saved in `_projects/` and `assets/images/behance/`.

For local use:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements.txt
.venv/bin/python scripts/sync_behance.py --dry-run
.venv/bin/python scripts/sync_behance.py
```

Local Jekyll preview/builds use saved content and never fetch Behance automatically. The importer runs separately or through GitHub Actions. A manually saved public profile HTML file can also be supplied with `--profile-html path/to/profile.html`; optional saved project files named `PROJECT_ID.html` can be supplied with `--project-html-dir path/to/pages`. In this mode it reads the supplied HTML and downloads discovered public cover assets, without requesting Behance profile/project pages. Only cards present in the saved file are imported.

### Keeping your edits during sync

New project filenames come from their titles, such as `_projects/surface-embellishment-portfolio.md`. Duplicate names receive an ID suffix. Unicode names are supported. Existing files were renamed to project names; explicit `permalink` fields preserve their previous page URLs. Later syncs match Behance IDs and keep existing filenames/URLs stable even if a title changes. Custom pages with no Behance URL are left alone. Projects are never automatically deleted because they disappear from Behance or a fetch fails.

Each imported record keeps its last source values under `behance_import`. On subsequent syncs, unchanged source-owned fields refresh; locally edited titles, categories, descriptions, or cover paths are kept. Unmodified timeline ranks refresh so new publications appear first; a manually changed `order` is preserved. Existing curated fields are kept on first adoption, while missing fields are filled. A byte-identical initial thumbnail can be adopted for future refreshes. Local changes to an imported image's bytes are also preserved. Markdown body, destination, visibility, focal point, and custom disc artwork are never overwritten. Clear a field to let the importer fill it again. Set `behance_sync: false` on a project to skip it completely. Avoid editing `behance_import` directly.

The About text reflects the owner's current focus: graphic design, textile roots, and exploration of motion/UX in tech. Edit `about`, `description`, and `socials` in `_config.yml` to update the bio, Behance, LinkedIn, email, or X links. Social links have matching icons and appear in a dedicated footer below the discs and in About. On phones, the links sit above the carousel arrows. The published contact email is the address supplied by the owner.

## Implementation choices

- Finite carousel with no autoplay. Soft ratchet sounds accompany movement by default, with no sound toggle. Browser audio rules may require a first tap, swipe, or key press before playback.
- Horizontal dragging and horizontal or vertical touch swipes browse the carousel. Swipe up/left for the next project and down/right for the previous one. Page scrolling remains normal outside the carousel and on case-study pages; pinch zoom stays available.
- Wheel/trackpad navigation is limited to the carousel region and releases scrolling at its ends; browser zoom gestures are preserved.
- Reduced motion removes easing; arrow buttons and keyboard navigation remain available.
- A project index and a no-JavaScript project list provide direct access to work.
- Returning from an internal page restores the viewed project for the current tab where session storage is available.

## Verification

Build with `./bin/bundle exec jekyll build --strict_front_matter`.

Run `python3 tests/content_check.py` to check local links and assets, internal Markdown pages, custom artwork overrides, hidden projects, and subpath deployment using a temporary copy of the content.

After installing `scripts/requirements.txt`, run `python3 -m unittest discover -s tests -p 'test_sync_behance.py' -v` for importer tests, including failed requests/assets, pagination, duplicate handling, local overrides, image edits, dry runs, and custom-page protection.

The browser regression check is `tests/browser_check.py` (Python with `websocket-client`). It expects a static server on port 4000 and an isolated Chromium/Edge browser with remote debugging on port 9222 and `--remote-allow-origins=http://localhost:9222`. Use a temporary browser profile. The check exercises mouse drag, wheel, touch swipe, keyboard controls, dialogs, reduced motion, responsive overflow, and the no-JavaScript fallback; it saves preview images in `docs/previews/`.
