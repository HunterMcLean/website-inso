# Drop-in URL workflow (for Claude / Cowork)

When Hunter pastes a URL in chat asking to add it, do this. Treat the workflow as one chat round-trip with one command for Hunter to run on his Mac.

## 1. Fetch & analyze

- `WebFetch` the URL. Read the page text, headings, meta description, visible CTAs, footer copy.
- If you want a quick visual, you can ask Hunter to share a screenshot from his browser, but **don't** try to capture screenshots from the sandbox — the proxy blocks the open web. Screenshot capture happens on his Mac in step 5.
- Use the page content + your training knowledge of the brand to score it.

## 2. Score against the canonical schema

Open `data/schema.json`. The microsite ONLY uses canonical values from Hunter's criteria doc — no Notion-only extras (Bento, Brutalism, Flat, Productivity, Communication, Apps, Social Media, etc. were dropped). Site Structure is retained in the data shape but hidden in the UI.

Score for:

- **Company Type** — `B2B` or `B2C`. Inferable from pricing/CTAs/audience.
- **Company Industry** — best 1–2 from the 21 canonical values. If it really doesn't fit any, ask Hunter whether to add it to canonical (don't silently invent values — `add_entry.py` will strip them).
- **Design Aesthetic** — best 1–3 from: Minimalist / Maximalist / Editorial / Grids / Skeuomorphism / Dark Mode.
- **Standout Elements** — pick the 3–6 most striking. Use the structured taxonomy in `schema.standoutElements` (Overall Styles / Atoms-Molecules-Organisms / Components / Pages). Only fill if confident from the page content.
- **Word Associations** — 3–6 from the canonical list of 27.
- **Industry Leader** — true if the brand is a clear category leader (Stripe, Linear, Vercel, Apple, etc.).
- **Unconventional** — true if it breaks expected patterns (brutalist, experimental typography, weird scroll behavior, etc.).
- **Typefaces** — read from page CSS or visible fonts.

Leave fields empty (not guessed) when uncertain — better to ship blanks than wrong tags.

## 3. Build the entry

Match the shape of any existing entry in `data/inspiration.json`. Keys you must produce:

```json
{
  "name": "Acme",
  "url": "https://acme.com",
  "companyType": ["B2B"],
  "companyIndustry": ["FinTech"],
  "designAesthetic": ["Minimalist"],
  "standoutElements": {
    "Overall Styles": ["Color Usage"],
    "Atoms/Molecules/Organisms": [],
    "Components": ["Hero"],
    "Pages": []
  },
  "wordAssociations": ["Modern", "Premium"],
  "industryLeader": false,
  "unconventional": false,
  "typefaces": ["Inter"]
}
```

`id`, `domain`, `siteStructure`, `screenshot`, `createdAt`, and `source` are filled in automatically by `add_url.py`.

## 4. Show Hunter the proposed entry

Render the JSON in chat with a one-line rationale per scored field if it's non-obvious. Ask: "Approve as-is, edit, or drop?"

## 5. On approval — write the pending file + give Hunter one command

Write the JSON to `data/_pending_add.json` (use the Edit/Write tool — Hunter doesn't need to copy/paste). Then tell him:

```sh
cd /Users/hmclean/Claudey/web-inspo-library
python3 scripts/add_url.py
./scripts/deploy.sh
```

`add_url.py` does:
1. Reads `data/_pending_add.json`.
2. Validates + canonicalizes via `add_entry.from_stdin`.
3. Refuses duplicates (offer `--replace` if Hunter says overwrite).
4. Appends to `data/inspiration.json` + keeps `data/inspiration.js` in sync.
5. Captures the screenshot via Playwright (1440 viewport → 800px JPEG q=72) and saves to `assets/screenshots/<id>.jpg`.
6. Updates the entry's `screenshot` field, saves again.
7. Deletes `_pending_add.json`.
8. Prints a deploy reminder.

Then `./scripts/deploy.sh` pushes to Netlify (~10s).

## 6. Edge cases

- **Already in the library**: `add_url.py` will refuse. Ask Hunter: "Already there — replace tags or skip?" If replace, he runs `python3 scripts/add_url.py --replace`.
- **URL is unreachable** (timeouts / cert errors / dead): suggest `python3 scripts/add_url.py --no-screenshot` so the entry still lands without a shot.
- **Screenshot looks wrong** (homepage redirected, login wall): re-capture later via `python3 scripts/capture_screenshots.py --only <id> --redo`.
- **Bulk submissions from the in-site form**: come into Hunter's email via Netlify Forms. Process them one by one through this same workflow.
