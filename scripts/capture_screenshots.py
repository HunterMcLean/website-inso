#!/usr/bin/env python3
"""
Capture screenshots for every inspiration.json entry that doesn't already
have one, save them to assets/screenshots/<id>.jpg at the canonical style
(1440 viewport, downscaled to 800px wide JPEG q=72), and write back the
new screenshot paths into inspiration.json + inspiration.js.

Run from the project root on your Mac (sandbox can't reach external sites):

    pip3 install playwright pillow --break-system-packages
    playwright install chromium
    python3 scripts/capture_screenshots.py

Flags:
    --only ID1,ID2,...   capture only these entries (by id)
    --redo               re-capture even if a screenshot already exists
    --limit N            stop after N captures (useful for smoke tests)
    --timeout MS         per-page timeout in milliseconds (default 25000)
    --concurrency N      number of pages in flight (default 4)
"""
import argparse
import json
import os
import sys
import re
import time
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("ERROR: playwright not installed. Run:\n  pip3 install playwright --break-system-packages\n  playwright install chromium")

try:
    from PIL import Image
except ImportError:
    sys.exit("ERROR: pillow not installed. Run: pip3 install pillow --break-system-packages")

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "data" / "inspiration.json"
JS_PATH = ROOT / "data" / "inspiration.js"
SHOTS_DIR = ROOT / "assets" / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

REPORT_PATH = ROOT / "data" / "screenshot-capture-report.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

VIEWPORT = {"width": 1440, "height": 900}
TARGET_WIDTH = 800
JPEG_QUALITY = 72


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated entry ids to capture")
    ap.add_argument("--redo", action="store_true", help="re-capture even if screenshot exists")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=25000)
    ap.add_argument("--concurrency", type=int, default=4)
    return ap.parse_args()


def select_entries(data, args):
    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    out = []
    for e in data["entries"]:
        if only:
            if e["id"] in only:
                out.append(e)
            continue
        if not args.redo and e.get("screenshot"):
            continue
        if not e.get("url"):
            continue
        out.append(e)
    if args.limit:
        out = out[: args.limit]
    return out


def normalize_url(url: str) -> str:
    if not url:
        return url
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def shot_path_for(entry):
    return SHOTS_DIR / f"{entry['id']}.jpg"


def downscale_to_jpeg(png_bytes: bytes, out_path: Path):
    with Image.open(BytesIO(png_bytes)) as im:
        im = im.convert("RGB")
        if im.width > TARGET_WIDTH:
            ratio = TARGET_WIDTH / im.width
            new_size = (TARGET_WIDTH, int(im.height * ratio))
            im = im.resize(new_size, Image.LANCZOS)
        im.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)


def capture_one(playwright, entry, timeout_ms):
    """Capture a single entry. Returns (ok, info_dict)."""
    url = normalize_url(entry["url"])
    info = {"id": entry["id"], "name": entry["name"], "url": url}
    browser = playwright.chromium.launch(headless=True)
    try:
        ctx = browser.new_context(viewport=VIEWPORT, user_agent=USER_AGENT, ignore_https_errors=True)
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Let above-the-fold lazy images settle
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except PWTimeout:
                pass
            time.sleep(1.0)
            png_bytes = page.screenshot(full_page=False, type="png")
        except PWTimeout as e:
            return False, {**info, "error": f"timeout: {e}"}
        except Exception as e:
            return False, {**info, "error": repr(e)}
        finally:
            ctx.close()
    finally:
        browser.close()

    out_path = shot_path_for(entry)
    try:
        downscale_to_jpeg(png_bytes, out_path)
    except Exception as e:
        return False, {**info, "error": f"image processing: {e}"}

    info["bytes"] = out_path.stat().st_size
    info["path"] = f"assets/screenshots/{out_path.name}"
    return True, info


def write_outputs(data):
    JSON_PATH.write_text(json.dumps(data, indent=2))
    js = "// Auto-generated. Same data as inspiration.json, exposed as window.INSPIRATION_DATA.\n"
    js += "window.INSPIRATION_DATA = " + json.dumps(data, indent=2) + ";\n"
    JS_PATH.write_text(js)


def main():
    args = parse_args()
    data = json.loads(JSON_PATH.read_text())
    targets = select_entries(data, args)
    if not targets:
        print("Nothing to capture.")
        return

    print(f"Capturing {len(targets)} screenshots → {SHOTS_DIR}")
    print(f"Concurrency: {args.concurrency}, timeout: {args.timeout}ms\n")

    by_id = {e["id"]: e for e in data["entries"]}
    results_ok, results_fail = [], []

    def worker(entry):
        # each thread owns its own playwright runtime
        with sync_playwright() as p:
            return capture_one(p, entry, args.timeout)

    started = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(worker, e): e for e in targets}
        for fut in as_completed(futures):
            entry = futures[fut]
            try:
                ok, info = fut.result()
            except Exception as e:
                ok, info = False, {"id": entry["id"], "name": entry["name"], "url": entry.get("url"), "error": f"unhandled: {e}"}
            done += 1
            if ok:
                results_ok.append(info)
                # update entry in-place
                by_id[info["id"]]["screenshot"] = info["path"]
                by_id[info["id"]]["screenshotCapturedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                size_kb = info["bytes"] // 1024
                print(f"[{done:>3}/{len(targets)}] OK   {info['name'][:30]:30}  {size_kb}KB")
            else:
                results_fail.append(info)
                print(f"[{done:>3}/{len(targets)}] FAIL {info['name'][:30]:30}  {info.get('error','?')[:60]}")
            # save progress every 10 successes
            if ok and len(results_ok) % 10 == 0:
                write_outputs(data)

    write_outputs(data)
    elapsed = time.time() - started

    REPORT_PATH.write_text(json.dumps({
        "ranAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": results_ok,
        "fail": results_fail,
    }, indent=2))

    print()
    print(f"Done in {elapsed:.0f}s.  ok: {len(results_ok)}  fail: {len(results_fail)}")
    print(f"Report: {REPORT_PATH.relative_to(ROOT)}")
    if results_fail:
        print("\nFailures (first 10):")
        for f in results_fail[:10]:
            print(f"  • {f['name']:30} {f.get('error','?')[:80]}")
        print("\nRetry failures with:")
        ids = ",".join(f["id"] for f in results_fail)
        print(f"  python3 scripts/capture_screenshots.py --only '{ids[:200]}{'...' if len(ids)>200 else ''}' --redo")


if __name__ == "__main__":
    main()
