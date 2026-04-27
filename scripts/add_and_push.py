#!/usr/bin/env python3
"""
Full pipeline: pending JSON → live on Netlify.

Single entry:
  python3 scripts/add_and_push.py
  (reads data/_pending_add.json, written by Claude)

Batch:
  python3 scripts/add_and_push.py --batch
  (reads data/_pending_batch.json — array of entry objects, written by Claude)

Steps:
  1. Pull latest from GitHub (rebase) so working tree is clean
  2. Validate + append entry/entries to inspiration.json, regen inspiration.js
  3. Capture screenshots via Playwright
  4. Commit + push → triggers Netlify rebuild (~30s)

Requires GITHUB_TOKEN in scripts/.env (see .env.example).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "scripts" / ".env"
PENDING = ROOT / "data" / "_pending_add.json"
PENDING_BATCH = ROOT / "data" / "_pending_batch.json"
DATA = ROOT / "data" / "inspiration.json"
SCHEMA = ROOT / "data" / "schema.json"
SHOTS_DIR = ROOT / "assets" / "screenshots"

sys.path.insert(0, str(ROOT / "scripts"))
import add_entry  # type: ignore  # noqa: E402


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def run(cmd, **kwargs):
    result = subprocess.run(cmd, cwd=ROOT, **kwargs)
    if result.returncode != 0:
        sys.exit(f"ERROR: command failed: {' '.join(str(c) for c in cmd)}")
    return result


def write_db(db):
    DATA.write_text(json.dumps(db, indent=2, ensure_ascii=False))
    js = "// Auto-generated. Same data as inspiration.json, exposed as window.INSPIRATION_DATA.\n"
    js += "window.INSPIRATION_DATA = " + json.dumps(db, indent=2, ensure_ascii=False) + ";\n"
    (ROOT / "data" / "inspiration.js").write_text(js)


def append_entries(payloads):
    schema = json.loads(SCHEMA.read_text())
    db = json.loads(DATA.read_text())
    existing_urls = {e["url"].rstrip("/") for e in db["entries"]}
    added = []
    for payload in payloads:
        url = payload.get("url", "").rstrip("/")
        if url in existing_urls:
            print(f"  SKIP (duplicate): {payload.get('name', url)}")
            continue
        entry = add_entry.from_stdin(payload, schema)
        db["entries"].append(entry)
        existing_urls.add(url)
        added.append(entry)
        print(f"  added: {entry['name']}")
    write_db(db)
    return db, added


def capture_screenshot(entry):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        from PIL import Image
    except ImportError:
        print(f"  WARNING: playwright/pillow not installed — skipping screenshot for {entry['name']}")
        return None

    url = entry["url"]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    out_path = SHOTS_DIR / f"{entry['id']}.jpg"
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    print(f"  → screenshot: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                      user_agent=ua, ignore_https_errors=True)
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                try:
                    page.wait_for_load_state("networkidle", timeout=4000)
                except PWTimeout:
                    pass
                time.sleep(1.0)
                png_bytes = page.screenshot(full_page=False, type="png")
            finally:
                ctx.close()
                browser.close()
    except Exception as e:
        print(f"    FAILED: {e}")
        return None

    with Image.open(BytesIO(png_bytes)) as im:
        im = im.convert("RGB")
        if im.width > 800:
            ratio = 800 / im.width
            im = im.resize((800, int(im.height * ratio)), Image.LANCZOS)
        im.save(out_path, "JPEG", quality=72, optimize=True, progressive=True)
    print(f"    saved ({out_path.stat().st_size // 1024}KB)")
    return f"assets/screenshots/{out_path.name}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", action="store_true", help="Read _pending_batch.json (array) instead of _pending_add.json")
    args = ap.parse_args()

    # --- Read pending entries ---
    if args.batch:
        if not PENDING_BATCH.exists():
            sys.exit(f"ERROR: no batch file at data/_pending_batch.json")
        payloads = json.loads(PENDING_BATCH.read_text())
        if not isinstance(payloads, list):
            sys.exit("ERROR: _pending_batch.json must be a JSON array")
    else:
        if not PENDING.exists():
            sys.exit(f"ERROR: no pending entry at data/_pending_add.json")
        payloads = [json.loads(PENDING.read_text())]

    # --- Load env ---
    env = load_env()
    token = env.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    owner = env.get("GITHUB_OWNER", "HunterMcLean")
    repo = env.get("GITHUB_REPO", "website-inso")
    branch = env.get("GITHUB_BRANCH", "main")

    if not token:
        sys.exit("ERROR: GITHUB_TOKEN not set.\n  Add it to scripts/.env:  GITHUB_TOKEN=ghp_...")

    push_url = f"https://{owner}:{token}@github.com/{owner}/{repo}.git"
    names = [p.get("name", p.get("id", "?")) for p in payloads]

    # --- Step 1: pull --rebase ---
    print("=== Step 1/4: Pulling latest from GitHub ===")
    run(["git", "pull", "--rebase", push_url, branch])

    # --- Step 2: append entries ---
    print(f"\n=== Step 2/4: Adding {len(payloads)} entr{'y' if len(payloads)==1 else 'ies'} ===")
    db, added = append_entries(payloads)
    if not added:
        print("Nothing new to add.")
        return

    # --- Step 3: screenshots ---
    print(f"\n=== Step 3/4: Capturing {len(added)} screenshot(s) ===")
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    for entry in added:
        rel = capture_screenshot(entry)
        if rel:
            for e in db["entries"]:
                if e["id"] == entry["id"]:
                    e["screenshot"] = rel
                    e["screenshotCapturedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    break
    write_db(db)

    # --- Clean up pending files ---
    for f in [PENDING, PENDING_BATCH]:
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass

    # --- Step 4: commit + push ---
    print("\n=== Step 4/4: Committing and pushing ===")
    files_to_add = ["data/inspiration.json", "data/inspiration.js"]
    for entry in added:
        shot = ROOT / "assets" / "screenshots" / f"{entry['id']}.jpg"
        if shot.exists():
            files_to_add.append(f"assets/screenshots/{entry['id']}.jpg")

    run(["git", "add"] + files_to_add)

    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if result.returncode == 0:
        print("Nothing to commit.")
        return

    label = names[0] if len(names) == 1 else f"{len(names)} sites: {', '.join(names)}"
    run(["git", "commit", "-m", f"Add {label}"])
    run(["git", "push", push_url, branch])

    print(f"\n✓ Done — live at https://whimsical-cupcake-98eda4.netlify.app in ~30s")
    print(f"  Added: {', '.join(e['name'] for e in added)}")


if __name__ == "__main__":
    main()
