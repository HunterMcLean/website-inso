# CLAUDE.md — Webstacks Inspiration Library

This file is read by Claude Code when working in this repo. It captures what's been built, how it works, where it lives, what's intentionally NOT done, and conventions to follow.

If anything below is out of date, update this file as part of the change.

---

## 1. What this is

A static, sortable/filterable web microsite the Webstacks design team uses to browse website inspiration. Source of truth: `data/inspiration.json` (~470 entries at last count, growing).

- **Live URL**: https://whimsical-cupcake-98eda4.netlify.app
- **Owner**: Hunter (hmclean@webstacks.com)
- **Audience**: Webstacks designers + curated submissions
- **Stack**: vanilla HTML/CSS/JS, no build step in the editor; Netlify hosts; one Netlify Function for live editor saves; one Netlify Form for designer submissions.

The criteria for what an "entry" looks like (taxonomy, fields) come from a doc Hunter wrote. The schema is canonical — anything not in the doc gets stripped on import.

---

## 2. Architecture

```
                          ┌─────────────────────────────────────────┐
                          │ whimsical-cupcake-98eda4.netlify.app    │
                          │  · static HTML/CSS/JS                   │
                          │  · Netlify Form: "submit-url"           │
                          │  · Netlify Function: save-inspiration   │
                          └────────────┬────────────────────────────┘
                                       │
                                       │ commits via GitHub Contents API (PAT)
                                       ▼
                       ┌──────────────────────────────────────┐
                       │ github.com/<owner>/web-inspo-library │
                       │  · main branch is canonical          │
                       │  · push triggers Netlify rebuild     │
                       └──────────────────────────────────────┘
                                       ▲
                                       │ git push (Hunter's Mac)
                                       │
                ┌──────────────────────────────────────┐
                │ /Users/hmclean/Claudey/web-inspo-…   │
                │  · same files as repo                │
                │  · helper scripts run here           │
                └──────────────────────────────────────┘
```

### Data flow when something changes

| Action | Trigger | Result |
|---|---|---|
| Edit tags in browser editor | "Save changes" button | POST `/.netlify/functions/save-inspiration` → commit to GitHub → rebuild |
| Submit a URL from the live site | Netlify Form `submit-url` | Stored in Netlify Forms dashboard + email Hunter |
| Hunter pastes a URL in chat | Manual workflow (see §6) | Claude writes `data/_pending_add.json` → Hunter runs `scripts/add_url.py` → `git push` |
| Bulk script run on Mac (rare) | e.g. screenshot capture | Local files updated → `git push` |
| Fallback zip deploy | `scripts/deploy.sh` | Bypasses GitHub. Site updates but JSON in repo is stale until next push. AVOID. |

### Why this shape

- **Static site**: zero runtime cost, instant page loads, easy to debug.
- **JSON as source of truth**: filter/search are fast in-memory; data is portable; no DB to manage.
- **GitHub-source deploys**: every save is a real commit, so every change is auditable + rollback-able with `git revert`.
- **One small Function**: only existing reason for serverless. Keeps the surface tiny.

---

## 3. Folder layout

```
web-inspo-library/
├── index.html                         # main page
├── assets/
│   ├── styles.css                     # all styles, single file
│   ├── app.js                         # all JS, single file (no build)
│   └── screenshots/                   # <id>.jpg — 800px JPEGs
├── data/
│   ├── inspiration.json               # SOURCE OF TRUTH
│   ├── inspiration.js                 # auto-generated shim, window.INSPIRATION_DATA, used for file:// preview
│   ├── schema.json                    # canonical taxonomy
│   ├── notion-mapping-report.json     # historical reference, not deployed
│   ├── figma-stubs-added.json         # historical reference, not deployed
│   └── *-report.json                  # screenshot/import reports, not deployed
├── netlify/
│   └── functions/
│       └── save-inspiration.js        # editor save endpoint
├── netlify.toml                       # build + functions config
├── scripts/
│   ├── add_entry.py                   # CLI: add a single entry
│   ├── add_url.py                     # one-shot: take pending JSON → entry + screenshot
│   ├── apply_edits.py                 # take downloaded JSON from editor fallback → write to disk
│   ├── build-inspiration-js.js        # Netlify build step: regen inspiration.js from inspiration.json
│   ├── capture_screenshots.py         # Playwright bulk capture
│   ├── deploy.sh                      # FALLBACK zip deploy (avoid; use git push)
│   ├── pull_submissions.py            # fetch new submit-url Netlify Form rows
│   ├── drop_in_workflow.md            # playbook for Claude when adding URLs from chat
│   └── .env.example                   # template (NETLIFY_AUTH_TOKEN for fallback deploy only)
├── docs/
│   └── github-netlify-setup.md        # one-time setup guide for the live save flow
├── start.command                      # double-click on macOS → local server
├── start.bat                          # Windows equivalent
├── .gitignore
├── README.md                          # user-facing
└── CLAUDE.md                          # this file
```

---

## 4. Data model

### Entry shape (`data/inspiration.json` → `entries[]`)

```json
{
  "id": "stripe-stripe-com",                    // slug(name)-slug(domain)
  "name": "Stripe",
  "url": "https://stripe.com",
  "domain": "stripe.com",
  "screenshot": "assets/screenshots/<id>.jpg",  // null/missing if not captured
  "companyType": ["B2B"],                       // array, single value usually
  "companyIndustry": ["FinTech", "Dev Tools"],
  "siteStructure": [],                          // RETAINED but not surfaced in UI
  "designAesthetic": ["Minimalist"],
  "standoutElements": {
    "Overall Styles": ["Gradient Usage"],
    "Atoms/Molecules/Organisms": [],
    "Components": ["Hero", "Trustbar"],
    "Pages": []
  },
  "wordAssociations": ["Modern", "Premium"],
  "industryLeader": true,
  "unconventional": false,
  "typefaces": ["Inter"],
  "createdAt": "...",
  "source": "manual-add" | "figma-export" | "notion-seed" | "claude-add"
}
```

### Canonical taxonomy

`data/schema.json` is the canonical list of allowed values. Any non-canonical values get **stripped silently** on import. Don't invent values — extend `schema.json` first if a value is genuinely missing, then ask Hunter to confirm before scoring entries with it.

The lists:

- **companyType** (1): `B2B`, `B2C`
- **companyIndustry** (21): AI, ML, Blockchain/Web3, FinTech, eCommerce, MarTech, Legal, Energy/Infrastructure, Real Estate, Manufacturing, Restaurants/Hospitality/Tourism, Logistics, Cybersecurity, Healthcare, Automotive/EV, HR Tech, Entertainment, Activism, Sales Tech, Dev Tools, Agency
- **designAesthetic** (6): Minimalist, Maximalist, Editorial, Grids, Skeuomorphism, Dark Mode
- **standoutElements** (grouped, ~30 total): see schema.json
- **wordAssociations** (27): Established, Youthful, Bright, Subtle, Punchy/Bold, Trendy, Classic, Authoritative, Friendly, Expensive, Economical, Serious, Playful, Mainstream, Unconventional, Natural, Industrial, Elite, Approachable, Modern, Traditional, Technical, Experiential, Dynamic, Static, Premium, Editorial
- **siteStructure** (4): retained in data only, hidden from UI

### `inspiration.js` is a build artifact

- Auto-generated from `inspiration.json` by `scripts/build-inspiration-js.js`
- Netlify build step regenerates it on every deploy
- Local scripts (`add_url.py`, `apply_edits.py`) also regenerate it
- It exists so `index.html` works under `file://` (no fetch())

If you ever edit `inspiration.json` by hand without using a script, you must re-run `node scripts/build-inspiration-js.js` (or any of the helper scripts that already do it) before testing locally under `file://`.

---

## 5. Front-end UI

### Browse mode (default)

- Sidebar: Type / Industries / Flags filters with counts
- Filter bar: Design System Elements / Design Aesthetic / Word Association dropdowns + sort + clear
- Grid of cards (12 per page) showing thumbnail + name + Industry tags + Word Association tags
- Click a card → detail dialog with all tags, Visit Site button, Download Screenshot button

### Edit mode (token-gated)

- Visible only if `localStorage.inspoEditToken` is set (visit site with `?edit=YOUR_SECRET` once)
- Same data, table view (25 rows per page)
- Inline chip editors for Industry / Aesthetic / Word Associations (× to remove, + Add → searchable popover)
- Single-pick for Type, toggles for flags
- "⋯" opens detail dialog in edit mode for advanced fields (standout elements grouped, typefaces text input)
- Floating save bar shows count of edited entries with **Save changes** + **Discard** actions
- "Save changes" POSTs to `/.netlify/functions/save-inspiration`; on failure offers to download patched JSON as fallback

### Submit-a-URL form

- "Submit an Inspo Site" button in header opens a modal
- Netlify Form (form name: `submit-url`)
- Fields: site_url (required), site_name, notes, submitter
- Honeypot field: bot-field
- AJAX submit + success state in the modal

### Important DOM IDs

- `#grid` — card grid
- `#edit-table-wrap` / `#edit-table` — edit-mode table
- `#detail` — entry detail dialog
- `#submit-dialog` — submit-a-URL modal
- `#save-bar` — sticky save bar (edit mode)
- `#popover-root` — popover host (when no dialog is open)

### Popover stacking gotcha (already solved, don't regress)

Native `<dialog>` puts itself + its `::backdrop` in the browser top layer. Anything appended to `<body>` renders **below** that. So when a popover (chip-add menu) needs to appear over a dialog, it must be appended to the dialog itself, not `#popover-root`. See `openPopover()` in `assets/app.js` — it picks `document.querySelector("dialog[open]")` as host when one is open.

Popover positioning is `position: fixed` so coordinates remain viewport-relative regardless of host.

---

## 6. Workflows

### Adding a URL via chat (most common)

**Fully automated — no approval step, no manual commands.**

Single URL:
1. WebFetch the URL.
2. Score against `data/schema.json`. Only canonical values. Leave fields blank if uncertain.
3. Write the entry to `data/_pending_add.json` (Write tool).
4. Run `python3 scripts/add_and_push.py` via Bash tool.
   This pulls, validates, appends, captures screenshot, commits, and pushes. Live in ~30s.

Multiple URLs (sent at once):
1. WebFetch all URLs in parallel.
2. Score each against schema.
3. Write all entries as a JSON array to `data/_pending_batch.json` (Write tool).
4. Run `python3 scripts/add_and_push.py --batch` via Bash tool.

If the Bash tool is unavailable or the run fails (e.g. Playwright timeout), fall back to telling Hunter to run the command manually.

### Adding via the in-site form

Designers paste URLs into the modal on the live site. Submissions land in Netlify Forms dashboard + email Hunter. To process them:

```sh
python3 scripts/pull_submissions.py
```

Outputs JSON for new submissions. Hunter pastes the JSON into Cowork, Claude scores each one and writes pending files, Hunter runs `add_url.py` for each in sequence.

There is no automated submission → entry pipeline. Don't try to build one without a webhook target — the sandbox can't reach `api.netlify.com`.

### Bulk re-categorizing

Visit the live site with `?edit=YOUR_SECRET` once. Click **Edit** to enter table view. Edit chips. Click **Save changes**. Function commits, GitHub triggers a rebuild, ~30s later the live site shows the new state.

If the function fails (token mismatch, API hiccup), the editor offers a download fallback → run `python3 scripts/apply_edits.py` from the project root → `git push`.

### Bulk screenshot capture

For entries missing a screenshot:

```sh
python3 scripts/capture_screenshots.py            # all missing
python3 scripts/capture_screenshots.py --limit 5  # smoke test
python3 scripts/capture_screenshots.py --only id1,id2 --redo
```

Uses Playwright + headless Chromium. 4 in parallel by default, ~25s timeout each. Failures are logged to `data/screenshot-capture-report.json`. Sandbox proxy blocks the open web — must run on Hunter's Mac.

### Deploys

- Normal: `git push` (with the Netlify-GitHub link from the setup doc).
- Fallback: `./scripts/deploy.sh` — zip deploy. Bypasses GitHub. **Only use if GitHub is down.** If you do this, the function-based saves can no longer fast-forward; you'll need to `git pull --rebase` and re-push to recover.

---

## 7. Conventions for Claude Code

### Editing source files

- **Single-file CSS, single-file JS**. Don't split into modules without a build step.
- **Vanilla DOM**. No framework, no jQuery, no build pipeline. Keep it that way unless there's a strong reason.
- **No new dependencies in `assets/app.js`**. The only third-party thing is the Inter font from Google Fonts.
- **All scripts are Python (stdlib + a couple of pip deps)** or Node (stdlib for the function). The function uses native `fetch` (Node 18+).

### Adding a new helper script

- Put it in `scripts/`
- Make it executable, run from project root
- Read paths via `Path(__file__).resolve().parent.parent` (Python) or `path.resolve(__dirname, "..")` (Node)
- Keep dependencies minimal (`json`, `pathlib`, `urllib.request` over `requests`); document any pip install in a leading comment
- Any state file lives in `data/_<name>.json` (underscored, gitignored, deploy-excluded)

### Adding a new entry-shape field

- Add the field to `data/schema.json` first (if it's a taxonomy)
- Update `add_entry.from_stdin` to validate/canonicalize the new field
- Update `assets/app.js` to render it (browse and/or edit modes)
- Update `data/inspiration.json` entries — but probably backfill via a one-off script
- Update §4 above

### Touching the function

`netlify/functions/save-inspiration.js` is small. Keep it small. Constraints:
- Constant-time token comparison (already there)
- Refuse empty entries arrays
- Only commits `data/inspiration.json` — `inspiration.js` is regenerated by the build, not by the function

### Sandbox reality check (for Claude in Cowork)

The Cowork sandbox proxy blocks: `api.netlify.com`, `api.github.com`, most arbitrary websites. It allows: `pypi.org`, the file system in `/Users/hmclean/Claudey/web-inspo-library`, and a few utility hosts.

If you need to do something that requires the open web (screenshots, GitHub commits, Netlify API), write a script Hunter runs on his Mac. Don't try to work around the proxy.

WebFetch is the one exception — it works for many domains for read-only HTML fetching.

### Tests

There are no automated tests. Validate by:
- Parsing JSON: `python3 -c "import json; json.load(open('data/inspiration.json'))"`
- Parsing JS: `node --check assets/app.js`
- Running `python3 scripts/build-inspiration-js.js` (technically Node — `node scripts/build-inspiration-js.js`)
- Loading `index.html` via `file://` after edits and clicking through

For changes to the editor's edit/save flow, test the round-trip end-to-end before assuming it works.

### Conventions for chat with Hunter

- He prefers concise replies, not lengthy preamble
- He's the design lead — speak to design intent over engineering minutiae unless he asks
- When proposing a JSON entry, show it as JSON and ask for approval before writing files
- He uses bash on macOS, `zsh` shell — write commands accordingly
- If a step requires running on his Mac (sandbox limitation), say so explicitly and provide the exact command
- Use `computer://` links when sharing files; absolute paths otherwise

---

## 8. State as of last update (2026-04-27)

- **Entries**: 470 (391 Notion-seeded + 78 Figma-export stubs + 1 manual add: Gradial)
- **Screenshots**: 450+ captured (~95% coverage)
- **Live URL**: https://whimsical-cupcake-98eda4.netlify.app
- **Last deploy method**: zip via `scripts/deploy.sh`
- **GitHub link**: pending Hunter creating the repo + connecting Netlify (in flight as of this doc)
- **Function**: code in repo but not yet deployed — first push to GitHub will activate it
- **Edit token**: not yet set (Hunter sets `EDIT_SECRET` in Netlify after step 5 of `docs/github-netlify-setup.md`)
- **Submit form**: live and tested with one submission
- **Deploy script**: works as fallback

### What's deployed live right now

The current Netlify deploy was made via zip-deploy. It includes:
- All current data (470 entries)
- The Submit-a-URL form
- The editor UI
- The save-inspiration function code is in the repo but the deploy was a zip without the netlify.toml's function config, so the endpoint may 404 on the currently-live deploy. **First action after GitHub setup: a fresh deploy from the new GitHub-linked Netlify config will activate the function.**

---

## 9. Roadmap / pending intentions

Sorted by priority Hunter has expressed.

### Imminent (Hunter's mid-setup)

- **Connect Netlify to GitHub** — see `docs/github-netlify-setup.md` steps 1-7. Hunter has done step 1 (created repo) and is on step 2 (push). Push is currently blocked on SSO; he's installing `gh` CLI to authenticate.

### Should-do soon

- **Score the 27 "uncertain" Figma stubs** — list is in commit history / `scripts/drop_in_workflow.md` notes. Names: Duna, Bird, Cake, Gradient Labs, Opencall, Frameship, rollups, Miter, Rogo, Headroom, delto, PROFounders, Mues.ai, Northlane, Garden Intel, SmarterSociety, Outchat.ai, Labaton, Dysrupt, TARS, Quicknote, Wonder, Rox, Telescope, Fin, Perk, Base. URLs were guessed; Hunter should eyeball each.
- **Standout elements scoring for the 78 Figma stubs** — left empty intentionally (needed visual review). Now that screenshots exist, Claude could pass through them with vision and propose values; Hunter would approve in batches.
- **Visual style refresh** — Hunter wanted the site's own design to match a Figma Sites reference. There's a roadmap line about this. No screenshot or reference URL was captured before context was lost. Ask before redesigning.

### Nice-to-have

- **Auto-create review tasks for incoming form submissions** — Cowork scheduled tasks can't reach Netlify API (sandbox), so this needs a different trigger. Options: (a) a small Mac launchd job that posts new submissions to a chat thread, (b) a Netlify outgoing webhook to a target Hunter controls. Discussed but not implemented.
- **Webhook so paste-in-chat directly opens a PR** — would let Claude open a draft PR with the new entry; Hunter merges. Skip if the editor save flow eats this use case.
- **Designer-self-serve edit access** — currently single shared token. If the team wants per-user audit, swap to Netlify Identity + role check in the function.

### Won't-build (decided against or impractical)

- Real-time form submission → Cowork task (no public webhook target for Cowork)
- Cron-driven scheduled task that polls Netlify Forms (sandbox blocks API)
- Backend database / migration to a non-static stack (overkill for the data shape)

---

## 10. Known issues / gotchas

- **The currently-deployed zip-deploy doesn't include `netlify/functions/`** — the function activates on the first GitHub-source deploy.
- **`inspiration.json` and `inspiration.js` can drift** if someone edits the JSON manually without running a script. The Netlify build catches this on deploy by regenerating, but local file:// preview won't reflect changes until you regenerate the JS shim.
- **`_pending_add.json`** is a transient handoff file. If a session ends mid-add and the file is left over, Hunter will see it on next add — `add_url.py` will prefer the leftover file over a fresh one. Fix: delete `data/_pending_add.json` before starting a new chat add.
- **Netlify Forms detection** runs at deploy time. If you edit the form HTML and break detection (remove `netlify` attribute, change form name, hide form behind JS-only DOM), Netlify won't process submissions. Test by inspecting `Forms` in the Netlify dashboard after each deploy that touches the form.
- **Edit mode View toggle is hidden without a token**. To regain access on a different browser: visit `?edit=THE_SECRET`. To clear: visit `?edit=off` or `?edit=logout`.
- **The fallback `deploy.sh`** bypasses GitHub. If you use it, the next save via the editor will conflict with the divergent state. Recovery: pull the live state via the Netlify CLI or just re-do edits on top of `git pull`.
- **`scripts/.env`** is for the legacy fallback deploy only (Netlify PAT). Don't put `EDIT_SECRET` or `GITHUB_TOKEN` there — those live in Netlify env vars and never touch local disk.

---

## 11. How to verify the system is healthy

Run from project root on Hunter's Mac (anything blocked says so):

```sh
# 1. Data parses
python3 -c "import json; d=json.load(open('data/inspiration.json')); print(len(d['entries']), 'entries')"

# 2. JS shim is in sync
node scripts/build-inspiration-js.js

# 3. Front-end JS is parseable
node --check assets/app.js

# 4. Function code is parseable
node --check netlify/functions/save-inspiration.js

# 5. Live site is up
curl -fsSI https://whimsical-cupcake-98eda4.netlify.app | head -1

# 6. Function endpoint responds (returns 401 without a token, which is correct)
curl -is -X POST https://whimsical-cupcake-98eda4.netlify.app/.netlify/functions/save-inspiration | head -1

# 7. Form is detected (look for "submit-url" in the HTML)
curl -fsS https://whimsical-cupcake-98eda4.netlify.app | grep -c 'name="submit-url"'
```

Healthy looks like: 470+ entries, build succeeds, JS parses, 200 from site, 401 from function, ≥1 from grep.
