#!/usr/bin/env python3
"""
One-shot "add a URL to the library" wrapper.

Pipeline:
  1. Read a single proposed entry JSON (default: data/_pending_add.json,
     written by Claude during a chat session). Or pass a path/use `-` for stdin.
  2. Validate + canonicalize via add_entry.from_stdin().
  3. Dedup by URL (refuses duplicates unless --replace).
  4. Append to data/inspiration.json + data/inspiration.js.
  5. Capture a screenshot via Playwright (1440 viewport, 800px JPEG q=72)
     and save to assets/screenshots/<id>.jpg.
  6. Update the entry's screenshot field, save again.
  7. Delete the pending JSON if it was the default file.
  8. Print next-step (deploy command).

Usage (designed for the chat workflow):
  # Claude writes data/_pending_add.json, then Hunter runs:
  python3 scripts/add_url.py

  # Or alternate forms:
  python3 scripts/add_url.py path/to/entry.json
  echo '<json>' | python3 scripts/add_url.py -
  python3 scripts/add_url.py --replace          # overwrite an existing URL
  python3 scripts/add_url.py --no-screenshot    # skip screenshot capture
"""
import argparse
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "inspiration.json"
DATA_JS = ROOT / "data" / "inspiration.js"
SCHEMA = ROOT / "data" / "schema.json"
PENDING = ROOT / "data" / "_pending_add.json"
SHOTS_DIR = ROOT / "assets" / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

# import add_entry helpers
sys.path.insert(0, str(ROOT / "scripts"))
import add_entry  # type: ignore  # noqa: E402


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default=None,
                    help="Path to entry JSON, or '-' for stdin. Default: data/_pending_add.json")
    ap.add_argument("--replace", action="store_true",
                    help="Overwrite an existing entry with the same URL.")
    ap.add_argument("--no-screenshot", action="store_true",
                    help="Skip screenshot capture (useful if the URL is unreachable).")
    ap.add_argument("--no-deploy-hint", action="store_true",
                    help="Don't print the deploy reminder at the end.")
    return ap.parse_args()


def load_payload(source):
    if source == "-":
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit("ERROR: no JSON on stdin.")
        return json.loads(raw), None
    path = Path(source) if source else PENDING
    if not path.exists():
        if source is None:
            sys.exit(
                f"ERROR: no pending entry at {path.relative_to(ROOT)}.\n"
                "  Claude should write the proposed entry there during the chat workflow."
            )
        sys.exit(f"ERROR: file not found: {path}")
    return json.loads(path.read_text()), path


def append_entry(payload, replace):
    schema = json.loads(SCHEMA.read_text())
    db = json.loads(DATA.read_text())
    entry = add_entry.from_stdin(payload, schema)

    existing_idx = next(
        (i for i, e in enumerate(db["entries"])
         if e["url"].rstrip("/") == entry["url"].rstrip("/")),
        None,
    )
    if existing_idx is not None and not replace:
        sys.exit(
            f"ERROR: duplicate URL already in library: {entry['url']}\n"
            "  Pass --replace to overwrite."
        )

    if existing_idx is not None:
        db["entries"][existing_idx] = entry
        action = "replaced"
    else:
        db["entries"].append(entry)
        action = "added"
    return db, entry, action


def write_db(db):
    DATA.write_text(json.dumps(db, indent=2, ensure_ascii=False))
    js = "// Auto-generated. Same data as inspiration.json, exposed as window.INSPIRATION_DATA.\n"
    js += "window.INSPIRATION_DATA = " + json.dumps(db, indent=2, ensure_ascii=False) + ";\n"
    DATA_JS.write_text(js)


def capture_screenshot(entry):
    """Best-effort screenshot. Returns the relative path on success, None on failure."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("WARNING: playwright not installed — skipping screenshot.")
        print("  pip3 install playwright && playwright install chromium")
        return None
    try:
        from PIL import Image
    except ImportError:
        print("WARNING: pillow not installed — skipping screenshot.")
        print("  pip3 install pillow")
        return None

    url = entry["url"]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"→ Capturing screenshot of {url}")
    out_path = SHOTS_DIR / f"{entry['id']}.jpg"
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=ua,
                ignore_https_errors=True,
            )
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
        print(f"  FAILED: {e}")
        return None

    with Image.open(BytesIO(png_bytes)) as im:
        im = im.convert("RGB")
        if im.width > 800:
            ratio = 800 / im.width
            im = im.resize((800, int(im.height * ratio)), Image.LANCZOS)
        im.save(out_path, "JPEG", quality=72, optimize=True, progressive=True)

    rel = f"assets/screenshots/{out_path.name}"
    size_kb = out_path.stat().st_size // 1024
    print(f"  saved {rel} ({size_kb}KB)")
    return rel


def main():
    args = parse_args()
    payload, source_path = load_payload(args.source)
    db, entry, action = append_entry(payload, args.replace)
    write_db(db)
    print(f"{action}: {entry['name']}  ({entry['url']})")

    if not args.no_screenshot:
        rel = capture_screenshot(entry)
        if rel:
            # rebuild the entry reference in db
            for e in db["entries"]:
                if e["id"] == entry["id"]:
                    e["screenshot"] = rel
                    e["screenshotCapturedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    break
            write_db(db)

    # Tidy up the pending file if that's what we read from
    if source_path and source_path == PENDING:
        try:
            source_path.unlink()
        except OSError:
            pass

    print(f"Total entries: {len(db['entries'])}")
    if not args.no_deploy_hint:
        print()
        print("Next: ./scripts/deploy.sh   (push to whimsical-cupcake-98eda4.netlify.app)")


if __name__ == "__main__":
    main()
