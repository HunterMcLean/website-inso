# Webstacks Inspiration Library

A static, sortable/filterable microsite for the design team's website inspiration. Front-end is vanilla HTML/CSS/JS (no build step). Source of truth is `data/inspiration.json`.

## Folder layout

```
web-inspo-microsite/
├── index.html
├── assets/
│   ├── styles.css
│   ├── app.js
│   └── screenshots/        ← drop HD PNGs here (named <id>.png or .jpg)
├── data/
│   ├── inspiration.json    ← single source of truth (391 entries seeded from Notion)
│   ├── inspiration.js      ← same data wrapped as window.INSPIRATION_DATA for file:// use
│   ├── schema.json         ← canonical filter taxonomy from the criteria doc
│   └── notion-mapping-report.json   ← what was preserved as “extras”, for review
├── scripts/
│   ├── add_entry.py            ← CLI for manual / programmatic additions
│   ├── capture_screenshots.py  ← bulk screenshot capture for entries missing one
│   ├── deploy.sh               ← push the current folder to Netlify
│   ├── .env.example            ← copy → .env and add your Netlify token
│   └── drop_in_workflow.md     ← how Claude handles "add this URL" requests
├── start.command           ← double-click on macOS to run a local server
├── start.bat               ← double-click on Windows
├── .gitignore
└── README.md
```

## Local preview

**Easiest: just double-click `index.html`.** The data is also written to `data/inspiration.js` (a small `window.INSPIRATION_DATA = …` shim) so the page works under `file://` with no server needed.

If you'd rather run a real server (e.g. to test the `fetch` path or use the script-based workflow):

- **macOS:** double-click `start.command` (it runs `python3 -m http.server 8765` and opens the page)
- **Windows:** double-click `start.bat`
- **Manual:**
  ```sh
  cd web-inspo-microsite
  python3 -m http.server 8765
  # open http://localhost:8765
  ```

## Deploy to Netlify

The site is live at https://whimsical-cupcake-98eda4.netlify.app.

### Primary: GitHub-source deploys (live save from the editor)

The recommended flow. Every save in the in-page editor commits to GitHub via a Netlify Function, which triggers a Netlify rebuild. ~30 seconds end-to-end.

One-time setup (GitHub repo + PAT + Netlify env vars + edit token):

→ See [`docs/github-netlify-setup.md`](docs/github-netlify-setup.md) for the step-by-step.

After that, normal "deploy" = save the JSON file via the editor. `git push` from the Mac also redeploys automatically.

### Fallback: zip deploy via `scripts/deploy.sh`

Still works as a manual fallback (e.g. if GitHub is down). Requires `scripts/.env` with a Netlify PAT (see `scripts/.env.example`). Run from the project root: `./scripts/deploy.sh`. Bypasses GitHub entirely; the function-based save flow won't pick up these changes until the next git push.

### Drag & drop

If neither works, drag the folder onto [app.netlify.com](https://app.netlify.com) → your site → **Deploys** → drop zone.

## Adding new inspiration

### Path 1 — paste a URL into chat (the workflow you asked for)

In a Cowork session, paste a URL like:

> Add this to the inspo library: https://example.com

I will:
1. Fetch the page (and take a screenshot if a browser connector is available).
2. Score it against your criteria schema (industry, aesthetic, standout elements, etc.) by reading page content + heuristics.
3. Show you the proposed entry as JSON for approval.
4. On your OK, append it to `data/inspiration.json` and (if connected) commit/push to GitHub → Netlify auto-deploys.

If a browser connector isn't connected, I'll generate the JSON entry for you and you drop a screenshot into `assets/screenshots/<id>.png` yourself.

### Path 2 — manual via script (for batch adds or drive-by additions)

JSON-piped form (used by Claude when adding from chat):
```sh
echo '{ ...entry json... }' | python3 scripts/add_entry.py --from-stdin
```

CLI-flag form (for quick by-hand additions):

```sh
python3 scripts/add_entry.py \
  --name "Linear" \
  --url "https://linear.app" \
  --industry "B2B,Dev Tools" \
  --aesthetic "Minimalist,Dark Mode" \
  --standout "Hero,Pricing Page,Microinteractions/Interactive UI" \
  --words "Modern,Premium,Subtle" \
  --typefaces "Inter,Tiempos" \
  --industry-leader \
  --screenshot "assets/screenshots/linear-linear-app.jpg"
```

Then commit & push.

### Bulk screenshot capture

For entries that don't yet have a screenshot, `scripts/capture_screenshots.py` will visit each URL with headless Chromium, take a 1440-wide viewport shot, downscale to 800px wide JPEG q=72, save to `assets/screenshots/<id>.jpg`, and write the path back into `data/inspiration.json` + `data/inspiration.js`.

One-time setup (your Mac, not the sandbox — Cowork's sandbox proxy blocks the open web):

```sh
pip3 install playwright pillow --break-system-packages
playwright install chromium
```

Run from the project root:

```sh
python3 scripts/capture_screenshots.py
```

Useful flags: `--only id1,id2` to retry specific entries, `--redo` to re-capture even if a screenshot exists, `--limit N` for a smoke test, `--concurrency N` (default 4). A per-run report is written to `data/screenshot-capture-report.json`.

## Schema (canonical, from your criteria doc)

| Field | Type | Source |
|---|---|---|
| Website Name | text | required |
| URL | link | required (dedup key) |
| HD Screenshot | image | optional, ideally `assets/screenshots/<id>.png` |
| Company Type | single (B2B/B2C) | dropdown |
| Company Industry | multi | 21 canonical values |
| Site Structure | single | retained in data, hidden from UI for now |
| Design Aesthetic | multi | 6 canonical values |
| Standout Design System Elements | multi, structured | grouped: Overall Styles / Atoms / Components / Pages |
| Word Associations | multi | 27 canonical |
| Industry Leader | yes/no | flag |
| Unconventional | yes/no | flag |
| Typefaces | text list | optional |

See `data/schema.json` for the exact value lists.

### Taxonomy policy

Only the canonical taxonomy from your criteria doc is used. Notion-only values
(Bento, Brutalism, Flat, Technology, Productivity, Apps, Communication, etc.)
were dropped on import. `add_entry.py` also strips any non-canonical values that
get passed in. Site Structure stays in the data shape but isn't surfaced in UI.

Pre-strip mapping report: `data/notion-mapping-report.json` (kept for reference).

## Roadmap (not built yet)

- HD screenshots from Figma file (in flight — pending bulk export)
- Visual style refresh to match the Figma Sites reference (in flight — pending screenshot)
- "Submit a URL" form embedded in the site for designers to self-serve (instead of going through Cowork)
- Webhook so paste-in-chat directly opens a PR in GitHub
