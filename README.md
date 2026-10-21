# PDF Free 4U

A self-hosted PDF workspace with a responsive browser interface, PDF-processing API, and SQLite job history.

## Included tools

- Merge PDFs in a chosen order
- Split a PDF into page files or selected page ranges
- Compress a PDF
- Rotate PDF pages
- Convert JPG and PNG images into a PDF

Generated files are isolated by browser session, can be downloaded or removed from recent history, and are automatically deleted after 24 hours. Uploads are processed in memory and are not retained. The upload limit is 100 MB total and each input PDF is limited to 1,500 pages.

## Run locally

Python 3.10 or newer is required.

```powershell
cd pdf-studio
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://localhost:8000`. The local server creates its SQLite database and output directory under `instance/`.

Run the integration tests with:

```powershell
python -m unittest discover -s tests -v
```

## Deploy with Docker Compose

1. Copy `.env.example` to `.env` and set `SECRET_KEY` to a unique random value. For example, generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
2. Run `docker compose up --build -d`.
3. Open `http://your-server:8000` (or the port set with `PORT`).

Compose uses a persistent Docker volume for both SQLite and generated downloads, runs the web process as a non-root user, and exposes `/healthz` for health checks. Back up the `paperplane-data` volume to preserve history and active downloads.

For a direct container deployment, provide `SECRET_KEY`, set `DATABASE_PATH` and `OUTPUT_DIR` to paths on persistent storage, and publish container port `8000`. Put the service behind an HTTPS reverse proxy in production.

## Deploy to Render Free

The included `render.yaml` defines a Docker web service on Render's Free plan and generates a secret key automatically. Connect a Git repository containing this project to Render and create the service from the Blueprint. If this project is inside a larger repository, set the Blueprint's root directory to `pdf-studio`.

No persistent disk is attached. The app still uses temporary filesystem space while it is running, but the SQLite history and generated downloads are lost when the free service spins down, restarts, or redeploys. Render's free web services can also sleep after 15 minutes without traffic and may take about a minute to wake. This configuration is best for a demo with small PDFs, not important or long-term files.

## Google Search indexing

The site exposes `/robots.txt` and `/sitemap.xml`, and its homepage includes a canonical URL and search/social metadata. After deploying these changes, add `https://pdffree4u.com/` as a Domain property in [Google Search Console](https://search.google.com/search-console/), verify ownership with the DNS TXT record Google provides, then submit `https://pdffree4u.com/sitemap.xml`. Use URL Inspection to request indexing of the homepage. Google controls whether and when a page is indexed or its position in search results; submission does not guarantee ranking.

## Deployment notes

The app is designed for one service instance with persistent local storage. Do not scale it horizontally without moving SQLite to a shared database and generated files to shared object storage. PDF processing runs synchronously in web workers; deployments handling untrusted or high-volume traffic should add resource limits and a background job queue. The default development secret is only for local use; always configure `SECRET_KEY` for a deployment.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Development-only value | Signs browser sessions; set a unique secret in deployment |
| `DATABASE_PATH` | `instance/jobs.sqlite3` | SQLite database location |
| `OUTPUT_DIR` | `instance/outputs` | Temporary generated downloads |
| `PORT` | `8000` | Local server port |