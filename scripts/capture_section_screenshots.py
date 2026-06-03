#!/usr/bin/env python3
"""
Section screenshot capture pipeline.

For each entry tagged with a component in standoutElements.Components, loads
the live URL and attempts to find + screenshot just that section.  Saves to:
  assets/screenshots/sections/<component-slug>/<id>.jpg

Does NOT modify inspiration.json or overwrite existing screenshots.

Usage (run from project root):
    # Smoke-test: 3 hero captures
    python3 scripts/capture_section_screenshots.py --component hero --limit 3

    # All hero sections
    python3 scripts/capture_section_screenshots.py --component hero

    # Specific entries
    python3 scripts/capture_section_screenshots.py --component switchback --only stripe-stripe-com,linear-linear-app

    # All components (long — run overnight)
    python3 scripts/capture_section_screenshots.py

    # Preview without saving
    python3 scripts/capture_section_screenshots.py --component hero --dry-run

Flags:
    --component SLUG    Only capture this component (see SLUG_MAP keys)
    --only IDs          Comma-separated entry IDs
    --limit N           Stop after N captures
    --redo              Re-capture even if a file already exists
    --concurrency N     Parallel workers (default 3)
    --timeout MS        Per-page timeout ms (default 28000)
    --dry-run           Run capture logic but don't write files

Dependencies (same as capture_screenshots.py):
    pip3 install playwright pillow --break-system-packages
    playwright install chromium
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("playwright not installed.\n  pip3 install playwright --break-system-packages\n  playwright install chromium")

try:
    from PIL import Image
except ImportError:
    sys.exit("pillow not installed.\n  pip3 install pillow --break-system-packages")

ROOT       = Path(__file__).resolve().parent.parent
JSON_PATH  = ROOT / "data" / "inspiration.json"
SHOTS_DIR  = ROOT / "assets" / "screenshots" / "sections"

VIEWPORT     = {"width": 1440, "height": 900}
TARGET_WIDTH = 800
JPEG_QUALITY = 72
USER_AGENT   = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Map schema display name → url-safe slug (must match SECTION_SLUGS in app.js)
SLUG_MAP = {
    "hero":             "Hero",
    "switchback":       "Switchback",
    "icon-card-deck":   "Icon Card Deck",
    "image-card-deck":  "Image Card Deck",
    "heading-block":    "Heading Block",
    "testimonials":     "Testimonials Section",
    "tabbed-switcher":  "Tabbed Switcher",
    "timed-switcher":   "Timed Switchers",
    "accordion":        "Accordions/FAQs",
    "trustbar":         "Trustbar",
    "conversion-panel": "Conversion Panel",
    "navigation":       "Primary Navigation",
    "mega-menu":        "Mega Menu",
    "footer":           "Footer",
    "case-study":       "Case Study Section",
    "search":           "Search Experience/Search Results",
}

# For each slug: ordered list of CSS selectors to try, then a fallback strategy.
# Fallback strategies: "viewport_top" | "scroll_bottom" | "scan_sections" | None
STRATEGIES = {
    "hero": {
        "selectors": [
            "[class*='hero' i]:not(header):not(nav)",
            "[id*='hero' i]",
            "main > section:first-of-type",
            "body > section:first-of-type",
            "main > div:first-of-type > section:first-of-type",
        ],
        "fallback": "viewport_top",
        "padding": 0,
    },
    "navigation": {
        "selectors": [
            "header nav", "header", "[role='banner']",
            "[class*='navbar' i]", "[class*='nav-bar' i]", "[class*='site-header' i]",
        ],
        "fallback": "viewport_top_partial",
        "padding": 0,
    },
    "footer": {
        "selectors": [
            "footer", "[role='contentinfo']",
            "[class*='footer' i]", "[id*='footer' i]",
        ],
        "fallback": "scroll_bottom",
        "padding": 0,
    },
    "trustbar": {
        "selectors": [
            "[class*='trust' i]", "[class*='logo-bar' i]", "[class*='logobar' i]",
            "[class*='partner' i]", "[class*='client-logo' i]",
            "[class*='brand' i]:not(header)",
        ],
        "fallback": None,
        "padding": 20,
    },
    "switchback": {
        "selectors": [
            "[class*='switchback' i]", "[class*='alternating' i]",
            "[class*='feature-row' i]", "[class*='split-section' i]",
            "[class*='two-col' i]", "[class*='two-column' i]",
        ],
        "fallback": "scan_sections",
        "padding": 0,
    },
    "testimonials": {
        "selectors": [
            "[class*='testimonial' i]", "[class*='review' i]",
            "[class*='quote' i]", "[class*='social-proof' i]",
            "[class*='customer' i]:not(header)",
        ],
        "fallback": None,
        "padding": 0,
    },
    "tabbed-switcher": {
        "selectors": [
            "[role='tablist']", "[class*='tab-' i]",
            "[class*='tabs' i]", "[class*='switcher' i]",
        ],
        "fallback": None,
        "padding": 40,
    },
    "timed-switcher": {
        "selectors": [
            "[class*='carousel' i]", "[class*='slider' i]",
            "[class*='rotating' i]", "[class*='auto-play' i]",
        ],
        "fallback": None,
        "padding": 0,
    },
    "accordion": {
        "selectors": [
            "[class*='accordion' i]", "details",
            "[class*='faq' i]", "[class*='collapse' i]",
        ],
        "fallback": None,
        "padding": 20,
    },
    "conversion-panel": {
        "selectors": [
            "[class*='cta' i]:not(button):not(a)",
            "[class*='conversion' i]", "[class*='call-to-action' i]",
            "[class*='signup' i]", "[class*='get-started' i]",
        ],
        "fallback": None,
        "padding": 0,
    },
    "icon-card-deck": {
        "selectors": [
            "[class*='icon-card' i]", "[class*='feature-card' i]",
            "[class*='benefits' i]", "[class*='features-grid' i]",
            "[class*='card-grid' i]",
        ],
        "fallback": "scan_sections",
        "padding": 0,
    },
    "image-card-deck": {
        "selectors": [
            "[class*='image-card' i]", "[class*='blog-grid' i]",
            "[class*='post-grid' i]", "[class*='resource-grid' i]",
            "[class*='card-deck' i]",
        ],
        "fallback": "scan_sections",
        "padding": 0,
    },
    "heading-block": {
        "selectors": [
            "[class*='heading-block' i]", "[class*='section-header' i]",
            "[class*='page-header' i]:not(header)",
        ],
        "fallback": None,
        "padding": 20,
    },
    "mega-menu": {
        "selectors": [
            "[class*='mega-menu' i]", "[class*='megamenu' i]",
            "nav [class*='dropdown' i]",
        ],
        "fallback": None,
        "padding": 0,
    },
    "case-study": {
        "selectors": [
            "[class*='case-study' i]", "[class*='casestudy' i]",
            "[class*='success-story' i]", "[class*='customer-story' i]",
        ],
        "fallback": None,
        "padding": 0,
    },
    "search": {
        "selectors": [
            "[class*='search' i]:not(input):not(button)",
            "[role='search']",
        ],
        "fallback": None,
        "padding": 20,
    },
}


# ─── Cookie/consent blocking (same as other scripts) ─────────────────────────
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
(function(){
  const sels=['#onetrust-accept-btn-handler','.cc-btn.cc-allow','#cookiebanner-accept-btn','button[id*="accept-all"]','button[id*="acceptAll"]','#accept-cookies','.cookie-accept','[aria-label="Accept all cookies"]'];
  for(const s of sels){try{const e=document.querySelector(s);if(e&&e.offsetParent!==null){e.click();return;}}catch(e){}}
  const labels=new Set(['accept all','accept all cookies','accept cookies','i accept','i agree','agree','allow all','got it','ok']);
  for(const el of document.querySelectorAll('button,[role="button"]')){try{if(el.offsetParent!==null&&labels.has(el.textContent.trim().toLowerCase())){el.click();return;}}catch(e){}}
})();
"""


# ─── Image helpers ────────────────────────────────────────────────────────────

def crop_and_save(png_bytes: bytes, max_height: int = 900) -> bytes:
    """Downscale to TARGET_WIDTH, cap height, return JPEG bytes."""
    with Image.open(BytesIO(png_bytes)) as im:
        im = im.convert("RGB")
        if im.width > TARGET_WIDTH:
            ratio = TARGET_WIDTH / im.width
            new_h = int(im.height * ratio)
            im = im.resize((TARGET_WIDTH, new_h), Image.LANCZOS)
        if im.height > max_height:
            im = im.crop((0, 0, im.width, max_height))
        buf = BytesIO()
        im.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        return buf.getvalue()


# ─── Playwright capture ───────────────────────────────────────────────────────

def _load_page(playwright, url: str, timeout_ms: int):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browser = playwright.chromium.launch(headless=True)
    ctx = browser.new_context(viewport=VIEWPORT, user_agent=USER_AGENT, ignore_https_errors=True)
    page = ctx.new_page()
    for pat in CMP_BLOCK_PATTERNS:
        page.route(pat, lambda route: route.abort())
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=4000)
    except PWTimeout:
        pass
    try:
        page.evaluate(COOKIE_DISMISS_JS)
    except Exception:
        pass
    time.sleep(0.6)
    return browser, ctx, page


def capture_section(playwright, url: str, slug: str, timeout_ms: int) -> bytes:
    """
    Returns raw PNG bytes of the best-matching section, or raises on failure.
    """
    strategy = STRATEGIES.get(slug, {"selectors": [], "fallback": "viewport_top", "padding": 0})
    selectors = strategy["selectors"]
    fallback  = strategy["fallback"]
    padding   = strategy.get("padding", 0)

    browser, ctx, page = _load_page(playwright, url, timeout_ms)
    try:
        # 1. Try each selector in order
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                box = loc.bounding_box(timeout=3000)
                if not box or box["width"] < 100 or box["height"] < 40:
                    continue
                # Scroll element into view
                loc.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.3)
                # Screenshot the element with optional padding
                if padding:
                    # Expand clip region
                    clip = {
                        "x":      max(0, box["x"] - padding),
                        "y":      max(0, box["y"] - padding),
                        "width":  min(VIEWPORT["width"], box["width"] + padding * 2),
                        "height": min(2400, box["height"] + padding * 2),
                    }
                    return page.screenshot(clip=clip, full_page=False, type="png")
                else:
                    return loc.screenshot(type="png", timeout=5000)
            except Exception:
                continue

        # 2. Fallback strategies
        if fallback == "viewport_top":
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.2)
            return page.screenshot(full_page=False, type="png")

        if fallback == "viewport_top_partial":
            page.evaluate("window.scrollTo(0, 0)")
            return page.screenshot(clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": 120}, type="png")

        if fallback == "scroll_bottom":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.4)
            return page.screenshot(full_page=False, type="png")

        if fallback == "scan_sections":
            # Take full-page screenshot and crop to a mid-page section
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
            time.sleep(0.3)
            return page.screenshot(full_page=False, type="png")

        raise RuntimeError(f"No element found for {slug} and no fallback matched")

    finally:
        ctx.close()
        browser.close()


# ─── Worker ───────────────────────────────────────────────────────────────────

def process_entry(entry, slug: str, out_dir: Path, args) -> dict:
    out_path = out_dir / f"{entry['id']}.jpg"
    if out_path.exists() and not args.redo:
        return {"status": "skipped"}
    try:
        with sync_playwright() as p:
            png = capture_section(p, entry["url"], slug, args.timeout)
        jpg = crop_and_save(png, max_height=1000)
        if not args.dry_run:
            out_path.write_bytes(jpg)
        return {"status": "ok", "bytes": len(jpg)}
    except Exception as e:
        return {"status": "failed", "error": repr(e)}


# ─── Main ─────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="Capture section-specific screenshots")
    ap.add_argument("--component",   help="Component slug to capture (e.g. hero, switchback)")
    ap.add_argument("--only",        help="Comma-separated entry IDs")
    ap.add_argument("--limit",       type=int, default=0)
    ap.add_argument("--redo",        action="store_true", help="Re-capture even if file exists")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--timeout",     type=int, default=28000)
    ap.add_argument("--dry-run",     action="store_true")
    return ap.parse_args()


def main():
    args   = parse_args()
    data   = json.loads(JSON_PATH.read_text())
    entries_by_id = {e["id"]: e for e in data["entries"]}
    only = set(s.strip() for s in args.only.split(",")) if args.only else None

    # Determine which slugs to process
    if args.component:
        slugs = [args.component.lower().strip()]
        if slugs[0] not in SLUG_MAP:
            sys.exit(f"Unknown component slug '{slugs[0]}'.\nKnown slugs: {', '.join(sorted(SLUG_MAP))}")
    else:
        slugs = list(SLUG_MAP.keys())

    total_ok = total_skip = total_fail = 0

    for slug in slugs:
        schema_name = SLUG_MAP[slug]
        # Entries tagged with this component and having a URL
        targets = [
            e for e in data["entries"]
            if schema_name in (e.get("standoutElements") or {}).get("Components", [])
            and e.get("url")
            and (only is None or e["id"] in only)
        ]
        if args.limit:
            targets = targets[: args.limit]

        if not targets:
            print(f"[{slug}] No tagged entries found — skipping")
            continue

        out_dir = SHOTS_DIR / slug
        if not args.dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        dry = " [DRY RUN]" if args.dry_run else ""
        print(f"\n=== {schema_name} ({slug}) — {len(targets)} entries{dry} ===")

        ok = skip = fail = 0
        done = 0

        def worker(entry):
            return entry, process_entry(entry, slug, out_dir, args)

        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = {ex.submit(worker, e): e for e in targets}
            for fut in as_completed(futures):
                entry = futures[fut]
                try:
                    _, res = fut.result()
                except Exception as exc:
                    res = {"status": "failed", "error": str(exc)}
                done += 1
                s = res["status"]
                if s == "ok":
                    ok += 1
                    kb = res["bytes"] // 1024
                    print(f"  [{done:>4}/{len(targets)}] ✓  {entry['name'][:35]:35}  {kb}KB")
                elif s == "skipped":
                    skip += 1
                else:
                    fail += 1
                    print(f"  [{done:>4}/{len(targets)}] ✗  {entry['name'][:35]:35}  {res.get('error','?')[:60]}")

        print(f"  → Done: {ok} captured, {skip} skipped, {fail} failed")
        total_ok += ok; total_skip += skip; total_fail += fail

    print(f"\n{'─'*50}")
    print(f"Total: {total_ok} captured, {total_skip} skipped, {total_fail} failed")
    if args.dry_run:
        print("[DRY RUN] No files written.")


if __name__ == "__main__":
    main()
