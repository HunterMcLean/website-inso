#!/usr/bin/env python3
"""
Monthly screenshot refresh pipeline.

Recaptures every entry that has an existing screenshot, pixel-diffs the new
capture against the saved one, and only saves + commits when the page has
visually changed beyond a configurable threshold.

Run from the project root:
    python3 scripts/refresh_screenshots.py

Flags:
    --dry-run          Capture + compare but do NOT save or commit anything
    --threshold N      Mean pixel diff (0-255) required to count as "changed" (default 8 ≈ 3%)
    --only ID1,ID2,...  Refresh only these entry IDs
    --limit N          Stop after N entries (useful for smoke tests)
    --concurrency N    Parallel Playwright workers (default 4)
    --timeout MS       Per-page timeout in milliseconds (default 25000)

Dependencies (same as capture_screenshots.py):
    pip3 install playwright pillow --break-system-packages
    playwright install chromium
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("ERROR: playwright not installed.\n  pip3 install playwright --break-system-packages\n  playwright install chromium")

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:
    sys.exit("ERROR: pillow not installed.\n  pip3 install pillow --break-system-packages")

ROOT        = Path(__file__).resolve().parent.parent
JSON_PATH   = ROOT / "data" / "inspiration.json"
JS_PATH     = ROOT / "data" / "inspiration.js"
SHOTS_DIR   = ROOT / "assets" / "screenshots"
REPORT_PATH = ROOT / "data" / "screenshot-refresh-report.json"
ENV_FILE    = ROOT / "scripts" / ".env"

VIEWPORT      = {"width": 1440, "height": 900}
TARGET_WIDTH  = 800
JPEG_QUALITY  = 72
USER_AGENT    = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Block cookie-consent platforms so banners don't appear in diffs
CMP_BLOCK_PATTERNS = [
    "**://*.cookielaw.org/**", "**://optanon.blob.core.windows.net/**",
    "**://*.cookiebot.com/**", "**://*.truste.com/**",
    "**://cmp.osano.com/**",   "**://*.osano.com/**",
    "**://cmp.quantcast.com/**", "**://quantcast.mgr.consensu.org/**",
    "**://*.iubenda.com/**",   "**://app.termly.io/**", "**://*.termly.io/**",
    "**://*.cookieyes.com/**", "**://sdk.privacy-center.org/**",
    "**://*.usercentrics.eu/**", "**://*.usercentrics.com/**",
    "**://*.privacy-mgmt.com/**", "**://*.consensu.org/**",
    "**://*.cookieinformation.com/**", "**://cdn.cookie-script.com/**",
]

COOKIE_DISMISS_JS = """
(function () {
  const selectors = [
    '#onetrust-accept-btn-handler','#onetrust-pc-btn-handler',
    '.cc-btn.cc-allow','.cc-accept','#cookiebanner-accept-btn',
    '#cookiebot-accept-all','[data-testid*="cookie"][data-testid*="accept"]',
    'button[id*="accept-all"]','button[id*="acceptAll"]',
    'button[class*="accept-all"]','button[class*="acceptAll"]',
    '#accept-cookies','.cookie-accept','[aria-label="Accept all cookies"]',
    '[aria-label="Accept All Cookies"]',
  ];
  for (const sel of selectors) {
    try { const el = document.querySelector(sel); if (el && el.offsetParent !== null) { el.click(); return; } } catch(e) {}
  }
  const labels = new Set(['accept all','accept all cookies','accept cookies','accept & close','i accept','i agree','agree','agree to all','allow all','allow all cookies','got it','ok, got it','ok','continue','dismiss']);
  for (const el of document.querySelectorAll('button,[role="button"],a.btn')) {
    try { if (el.offsetParent !== null && labels.has(el.textContent.trim().toLowerCase())) { el.click(); return; } } catch(e) {}
  }
  const hideSelectors = ['#onetrust-consent-sdk','#onetrust-banner-sdk','#cookiebot','#CybotCookiebotDialog','.cc-window','.cc-banner','#cookie-law-info-bar','.cookie-law-info-bar','#qc-cmp2-container','#sp-cc','.sp-message-container','[id*="cookie-banner"]','[class*="cookie-banner"]','.cookieConsent','#cookieConsent','.cookie-notice','#cookie-notice','.cookie-popup','#cookie-popup'];
  for (const sel of hideSelectors) {
    try { document.querySelectorAll(sel).forEach(el => el.style.setProperty('display','none','important')); } catch(e) {}
  }
})();
"""


# ─── helpers ────────────────────────────────────────────────────────────────

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
        sys.exit(f"ERROR: {' '.join(str(c) for c in cmd)}")
    return result


def write_db(data):
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    js = "// Auto-generated. Same data as inspiration.json, exposed as window.INSPIRATION_DATA.\n"
    js += "window.INSPIRATION_DATA = " + json.dumps(data, indent=2, ensure_ascii=False) + ";\n"
    JS_PATH.write_text(js)


def downscale_to_jpeg(png_bytes: bytes, quality=JPEG_QUALITY) -> bytes:
    """Return JPEG bytes at TARGET_WIDTH, without saving to disk."""
    with Image.open(BytesIO(png_bytes)) as im:
        im = im.convert("RGB")
        if im.width > TARGET_WIDTH:
            ratio = TARGET_WIDTH / im.width
            im = im.resize((TARGET_WIDTH, int(im.height * ratio)), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        return buf.getvalue()


def pixel_diff_mean(existing_path: Path, new_jpg_bytes: bytes) -> float:
    """
    Mean per-channel pixel difference between the saved screenshot and the new
    capture. Returns 0.0–255.0; higher = more changed.
    Returns 255.0 if the existing file is missing or comparison fails.
    """
    if not existing_path.exists():
        return 255.0
    try:
        with Image.open(existing_path) as old_im, Image.open(BytesIO(new_jpg_bytes)) as new_im:
            old_rgb = old_im.convert("RGB")
            new_rgb = new_im.convert("RGB")
            # Resize to match existing dimensions so diff is channel-accurate
            if old_rgb.size != new_rgb.size:
                new_rgb = new_rgb.resize(old_rgb.size, Image.LANCZOS)
            diff = ImageChops.difference(old_rgb, new_rgb)
            stat = ImageStat.Stat(diff)
            return sum(stat.mean) / max(len(stat.mean), 1)
    except Exception:
        return 255.0


# ─── capture ────────────────────────────────────────────────────────────────

def capture_png(playwright, url: str, timeout_ms: int):
    """Returns raw PNG bytes, or raises on failure."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browser = playwright.chromium.launch(headless=True)
    try:
        ctx = browser.new_context(viewport=VIEWPORT, user_agent=USER_AGENT, ignore_https_errors=True)
        page = ctx.new_page()
        for pattern in CMP_BLOCK_PATTERNS:
            page.route(pattern, lambda route: route.abort())
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except PWTimeout:
                pass
            try:
                page.evaluate(COOKIE_DISMISS_JS)
            except Exception:
                pass
            time.sleep(0.8)
            return page.screenshot(full_page=False, type="png")
        finally:
            ctx.close()
    finally:
        browser.close()


def process_entry(entry, args):
    """
    Capture, diff, decide. Returns a result dict:
      status: "changed" | "unchanged" | "failed"
      diff:   float (mean pixel diff)
      bytes:  int (new file size if saved)
      error:  str (if failed)
      new_jpg_bytes: bytes | None (if changed, caller saves to disk)
    """
    shot_path = SHOTS_DIR / f"{entry['id']}.jpg"
    try:
        with sync_playwright() as p:
            png_bytes = capture_png(p, entry["url"], args.timeout)
    except Exception as e:
        return {"status": "failed", "error": repr(e)}

    new_jpg = downscale_to_jpeg(png_bytes)
    diff = pixel_diff_mean(shot_path, new_jpg)

    if diff <= args.threshold:
        return {"status": "unchanged", "diff": diff}

    return {"status": "changed", "diff": diff, "new_jpg_bytes": new_jpg, "bytes": len(new_jpg)}


# ─── main ────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="Monthly screenshot refresh")
    ap.add_argument("--dry-run",     action="store_true", help="Compare only, do not save or commit")
    ap.add_argument("--threshold",   type=float, default=8.0, help="Mean pixel diff to count as changed (default 8)")
    ap.add_argument("--only",        help="Comma-separated entry IDs to refresh")
    ap.add_argument("--limit",       type=int,   default=0)
    ap.add_argument("--concurrency", type=int,   default=4)
    ap.add_argument("--timeout",     type=int,   default=25000)
    return ap.parse_args()


def main():
    args = parse_args()

    data    = json.loads(JSON_PATH.read_text())
    by_id   = {e["id"]: e for e in data["entries"]}
    only    = set(s.strip() for s in args.only.split(",")) if args.only else None

    # Select entries that already have a screenshot (nothing to compare otherwise)
    targets = [
        e for e in data["entries"]
        if e.get("screenshot") and e.get("url")
        and (only is None or e["id"] in only)
    ]
    if args.limit:
        targets = targets[: args.limit]

    if not targets:
        print("No entries with existing screenshots found.")
        return

    env   = load_env()
    token = env.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    owner = env.get("GITHUB_OWNER", "HunterMcLean")
    repo  = env.get("GITHUB_REPO",  "website-inso")
    branch = env.get("GITHUB_BRANCH", "main")

    if not args.dry_run:
        if not token:
            sys.exit("ERROR: GITHUB_TOKEN not set in scripts/.env")
        push_url = f"https://{owner}:{token}@github.com/{owner}/{repo}.git"
        print("=== Step 1/3: Pulling latest from GitHub ===")
        run(["git", "pull", "--rebase", push_url, branch])

    dry_label = " [DRY RUN]" if args.dry_run else ""
    print(f"\n=== Refreshing {len(targets)} screenshots{dry_label} ===")
    print(f"Threshold: >{args.threshold:.1f} mean pixel diff  |  Concurrency: {args.concurrency}\n")

    results_changed  = []
    results_unchanged = []
    results_failed   = []
    now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    done   = 0

    def worker(entry):
        return entry, process_entry(entry, args)

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(worker, e): e for e in targets}
        for fut in as_completed(futures):
            entry = futures[fut]
            try:
                _, res = fut.result()
            except Exception as exc:
                res = {"status": "failed", "error": str(exc)}

            done += 1
            status = res["status"]
            diff_str = f"diff={res.get('diff', 0):.1f}" if "diff" in res else ""

            if status == "changed":
                results_changed.append({"id": entry["id"], "name": entry["name"], "diff": res.get("diff", 0)})
                size_kb = res["bytes"] // 1024
                print(f"[{done:>4}/{len(targets)}] CHANGED   {entry['name'][:32]:32}  {diff_str}  {size_kb}KB")
                if not args.dry_run:
                    shot_path = SHOTS_DIR / f"{entry['id']}.jpg"
                    shot_path.write_bytes(res["new_jpg_bytes"])
                    by_id[entry["id"]]["screenshotUpdatedAt"] = now_ts
                    by_id[entry["id"]]["screenshotCapturedAt"] = now_ts
            elif status == "unchanged":
                results_unchanged.append({"id": entry["id"], "name": entry["name"], "diff": res.get("diff", 0)})
                print(f"[{done:>4}/{len(targets)}] unchanged {entry['name'][:32]:32}  {diff_str}")
            else:
                results_failed.append({"id": entry["id"], "name": entry["name"], "error": res.get("error", "?")})
                print(f"[{done:>4}/{len(targets)}] FAILED    {entry['name'][:32]:32}  {res.get('error','?')[:60]}")

    # ── Summary ──
    print(f"\nChecked: {len(targets)}  Changed: {len(results_changed)}  "
          f"Unchanged: {len(results_unchanged)}  Failed: {len(results_failed)}")

    # ── Write report ──
    report = {
        "ranAt": now_ts, "dryRun": args.dry_run,
        "threshold": args.threshold,
        "summary": {"checked": len(targets), "changed": len(results_changed),
                    "unchanged": len(results_unchanged), "failed": len(results_failed)},
        "changed": results_changed, "failed": results_failed,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"Report: {REPORT_PATH.relative_to(ROOT)}")

    if args.dry_run:
        print("\n[DRY RUN] No files written. Re-run without --dry-run to apply changes.")
        return

    if not results_changed:
        print("\nNo screenshots changed — nothing to commit.")
        return

    # ── Write JSON/JS + commit ──
    print(f"\n=== Step 2/3: Writing updated data ===")
    write_db(data)

    print(f"=== Step 3/3: Committing and pushing ===")
    files_to_add = ["data/inspiration.json", "data/inspiration.js"]
    for r in results_changed:
        files_to_add.append(f"assets/screenshots/{r['id']}.jpg")

    run(["git", "add"] + files_to_add)

    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if result.returncode == 0:
        print("Nothing staged — skipping commit.")
        return

    names_preview = ", ".join(r["name"] for r in results_changed[:5])
    if len(results_changed) > 5:
        names_preview += f" +{len(results_changed)-5} more"
    push_url = f"https://{owner}:{token}@github.com/{owner}/{repo}.git"
    run(["git", "commit", "-m",
         f"chore: refresh {len(results_changed)} screenshot(s) — {names_preview}"])
    run(["git", "push", push_url, branch])

    print(f"\n✓ Done — {len(results_changed)} screenshot(s) updated, live in ~30s")
    if results_failed:
        print(f"\nRetry {len(results_failed)} failure(s) with:")
        ids = ",".join(r["id"] for r in results_failed)
        print(f"  python3 scripts/refresh_screenshots.py --only '{ids[:200]}'")


if __name__ == "__main__":
    main()
