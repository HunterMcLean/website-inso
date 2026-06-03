#!/usr/bin/env python3
"""
Section screenshot capture pipeline — layered detection.

For each entry tagged with a component in standoutElements.Components, loads
the live URL and attempts to find + screenshot just that section.  Saves to:
  assets/screenshots/sections/<component-slug>/<id>.jpg

Does NOT modify inspiration.json or overwrite existing full-page screenshots.

── How detection works (stack-agnostic, in priority order) ───────────────────
Modern marketing sites name things wildly differently (Tailwind has no semantic
class names; styled-components/Framer hash them; Divi/HubSpot reuse one generic
wrapper class everywhere). So class-name matching is the WEAKEST signal and runs
last. Each component is detected by trying these layers in order:

  1. landmark   — HTML5 semantics (<header>/<nav>/<footer>/[role=...]). Rock-solid.
  2. aria       — ARIA interaction patterns ([role=tablist], [aria-expanded]).
  3. semantic   — meaningful elements (<details>, <blockquote>).
  4. heading    — scan headings for keyword text ("what our customers say"), grab
                  the section ancestor. Works regardless of class names.
  5. geometry   — rendered layout shape: a Switchback is an image+text 2-col row;
                  a Card Deck is 3+ similarly-sized siblings. Independent of markup.
  6. class      — class/id keyword match. Last resort, well-named sites only.
  7. positional — viewport-top (hero) / scroll-bottom (footer) fallback.

Every capture records which layer fired + a confidence rating into
data/section-capture-report.json so coverage is measurable, never assumed.
Hard components that match nothing are recorded as "missed" and NO file is
written — the UI then shows the labelled full-page fallback instead of a
misleading crop.

── Usage (run from project root) ─────────────────────────────────────────────
    # Smoke-test: 3 hero captures
    python3 scripts/capture_section_screenshots.py --component hero --limit 3

    # All hero sections
    python3 scripts/capture_section_screenshots.py --component hero

    # Specific entries
    python3 scripts/capture_section_screenshots.py --component switchback --only stripe-stripe-com

    # All components (long — run overnight)
    python3 scripts/capture_section_screenshots.py

    # Preview + coverage report without saving
    python3 scripts/capture_section_screenshots.py --component switchback --dry-run

Flags:
    --component SLUG    Only capture this component (see SLUG_MAP keys)
    --only IDs          Comma-separated entry IDs
    --limit N           Stop after N entries per component
    --redo              Re-capture even if a file already exists
    --concurrency N     Parallel workers (default 3)
    --timeout MS        Per-page timeout ms (default 28000)
    --dry-run           Run detection + report but don't write image files
    --vision            On DOM misses, ask Claude to locate the section in a
                        full-page screenshot. Only fires for static components
                        (conversion-panel, accordion, case-study, testimonials,
                        trustbar, switchback) — never interaction-gated ones.
                        Needs ANTHROPIC_API_KEY in scripts/.env or the env.
    --vision-model M    Override vision model (default claude-sonnet-4-5;
                        or set ANTHROPIC_MODEL).

Examples with vision:
    # Re-run accordion misses with the vision backstop (skips already-captured files)
    python3 scripts/capture_section_screenshots.py --component accordion --vision
    # Vision sweep of all static components
    python3 scripts/capture_section_screenshots.py --vision

Dependencies (same as capture_screenshots.py):
    pip3 install playwright pillow --break-system-packages
    playwright install chromium

Vision adds NO new pip deps — it calls the Anthropic API directly via urllib.
Cost is tiny (~1 small image + <200 tokens per missed site).
"""

import argparse
import base64
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
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

ROOT        = Path(__file__).resolve().parent.parent
JSON_PATH   = ROOT / "data" / "inspiration.json"
SHOTS_DIR   = ROOT / "assets" / "screenshots" / "sections"
REPORT_PATH = ROOT / "data" / "section-capture-report.json"

VIEWPORT      = {"width": 1440, "height": 900}
TARGET_WIDTH  = 800
JPEG_QUALITY  = 72
MAX_ELEM_H    = 1600   # px (pre-downscale): taller than this → viewport capture instead
USER_AGENT    = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# slug → schema display name. Slugs MUST match SECTION_SLUGS in assets/app.js.
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
    "dropdown-menu":    "Dropdown Menu",
    "search":           "Search Experience/Search Results",
    "case-study":       "Case Study Section",
    "footer":           "Footer",
}

# slugs that have a reliable positional fallback worth saving when detection misses
POSITIONAL_FALLBACK = {"hero": "top", "navigation": "top", "footer": "bottom"}

# Components where a Claude-vision backstop is worth running on DOM misses.
# Only STATIC, visually-distinct sections — NOT interaction-gated ones (mega-menu
# hover, tabbed/timed switchers, search) where a static screenshot is meaningless.
VISION_COMPONENTS = {"conversion-panel", "accordion", "case-study", "testimonials", "trustbar", "switchback"}

# Set in main() when --vision is passed.
VISION_API_KEY = ""
VISION_MODEL   = "claude-sonnet-4-5"   # override with --vision-model or ANTHROPIC_MODEL
VISION_ENABLED = False
ENV_FILE       = ROOT / "scripts" / ".env"


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


# ─── Layered detection (runs in the page; tags the winning element) ──────────
# Returns {found, layer, confidence, w, h}. When found, marks the element with
# data-wsdetect="1" so Python can locate + screenshot it without coordinate math.
DETECT_JS = r"""
(slug) => {
  document.querySelectorAll('[data-wsdetect]').forEach(e => e.removeAttribute('data-wsdetect'));
  const vw = window.innerWidth;

  const rectOf = el => { const r = el.getBoundingClientRect(); return {w:r.width, h:r.height, top:r.top, left:r.left}; };
  const visible = el => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 80 || r.height < 30) return false;
    const st = getComputedStyle(el);
    if (st.display==='none' || st.visibility==='hidden' || parseFloat(st.opacity||'1')===0) return false;
    return true;
  };
  const txt = el => (el.textContent||'').trim().toLowerCase().replace(/\s+/g,' ');

  // climb to the nearest full-width section-like ancestor (capped so we don't grab the whole page)
  const sectionAncestor = el => {
    let cur = el;
    for (let i=0; i<7 && cur && cur.parentElement; i++) {
      const tag = cur.tagName.toLowerCase();
      const r = cur.getBoundingClientRect();
      if ((tag==='section' || tag==='article') && r.height>120 && r.height<1600) return cur;
      if (cur.matches && cur.matches('[class*="section" i]') && r.width>=vw*0.7 && r.height>120 && r.height<1600) return cur;
      cur = cur.parentElement;
    }
    cur = el;
    for (let i=0; i<8 && cur && cur.parentElement; i++) {
      const r = cur.getBoundingClientRect();
      if (r.width >= vw*0.8 && r.height >= 150) return cur;
      cur = cur.parentElement;
    }
    return el;
  };

  const firstVisible = sels => {
    for (const s of sels) { try { const e = document.querySelector(s); if (visible(e)) return e; } catch(_){} }
    return null;
  };

  const headingScan = keywords => {
    const heads = document.querySelectorAll('h1,h2,h3,h4,[class*="heading" i],[class*="title" i]');
    for (const h of heads) {
      const t = txt(h);
      if (!t || t.length>140) continue;
      if (keywords.some(k => t.includes(k))) {
        const sec = sectionAncestor(h);
        if (visible(sec)) return sec;
      }
    }
    return null;
  };

  // 3+ similarly-sized sibling children → a card deck. needImg: true=image cards, false=icon cards.
  const deckScan = (minN, needImg) => {
    let best=null, bestScore=0;
    for (const p of document.querySelectorAll('ul,ol,div,section')) {
      const kids = Array.from(p.children).filter(c => { const r=c.getBoundingClientRect(); return r.width>90 && r.height>80; });
      if (kids.length < minN) continue;
      const ws = kids.map(k => k.getBoundingClientRect().width);
      const hs = kids.map(k => k.getBoundingClientRect().height);
      const avgW = ws.reduce((a,b)=>a+b,0)/ws.length;
      const avgH = hs.reduce((a,b)=>a+b,0)/hs.length;
      if (avgW < 120 || avgH < 80) continue;
      if (!ws.every(w => Math.abs(w-avgW) < avgW*0.28)) continue;     // similar widths
      if (!hs.every(h => Math.abs(h-avgH) < avgH*0.45)) continue;     // roughly similar heights
      const withImg = kids.filter(k => k.querySelector('img,picture')).length;
      const withSvg = kids.filter(k => k.querySelector('svg')).length;
      if (needImg === true  && withImg < kids.length*0.6) continue;
      if (needImg === false) { if (withImg > kids.length*0.5) continue; if (withSvg < kids.length*0.4) continue; }
      const score = kids.length * Math.min(avgH, 380);
      if (score > bestScore) { bestScore = score; best = sectionAncestor(p); }
    }
    return best;
  };

  // a Switchback: section containing a 2-col row, one column an image, the other text
  const switchbackScan = () => {
    let best=null, bestScore=0;
    for (const s of document.querySelectorAll('section,div')) {
      const r = s.getBoundingClientRect();
      if (r.width < vw*0.6 || r.height < 220 || r.height > 950) continue;
      const conts = [s, ...s.querySelectorAll(':scope > div, :scope > div > div')];
      for (const c of conts) {
        const cc = Array.from(c.children).filter(x => { const xr=x.getBoundingClientRect(); return xr.width>100 && xr.height>100; });
        if (cc.length !== 2) continue;
        const [a,b] = cc;
        const ar=a.getBoundingClientRect(), br=b.getBoundingClientRect();
        if (Math.abs(ar.top-br.top) > Math.max(ar.height,br.height)*0.5) continue;  // must share a row
        const aMedia = a.querySelector('img,picture,svg,video'), bMedia = b.querySelector('img,picture,svg,video');
        const aText = txt(a).length>30, bText = txt(b).length>30;
        if ((aMedia && bText && !aText) || (bMedia && aText && !bText)) {
          const score = r.width * Math.min(r.height, 500);
          if (score > bestScore) { bestScore = score; best = s; }
        }
      }
    }
    return best;
  };

  const mark = (el, layer, confidence) => {
    el.setAttribute('data-wsdetect','1');
    const r = rectOf(el);
    return {found:true, layer, confidence, w:Math.round(r.w), h:Math.round(r.h)};
  };

  let el=null, layer=null, conf=null;

  switch (slug) {
    case 'navigation':
      el = firstVisible(['header nav','header[role="banner"]','[role="banner"]','header','[class*="navbar" i]','[class*="site-header" i]']);
      if (el) { layer='landmark'; conf='high'; }
      break;

    case 'footer':
      el = firstVisible(['footer','[role="contentinfo"]','[class*="site-footer" i]','[class*="footer" i]']);
      if (el) { layer='landmark'; conf='high'; }
      break;

    case 'hero': {
      const main = document.querySelector('main') || document.body;
      for (const s of Array.from(main.children)) {
        if (!visible(s)) continue;
        const tag = s.tagName.toLowerCase();
        if (tag==='header' || (s.matches && s.matches('nav,[role="banner"]'))) continue;
        if (s.getBoundingClientRect().height > 200) { el = s; break; }
      }
      if (el) { layer='positional'; conf='high'; }
      break;
    }

    case 'tabbed-switcher':
      el = firstVisible(['[role="tablist"]']);
      if (el) { el = sectionAncestor(el); layer='aria'; conf='high'; }
      else { el = firstVisible(['[class*="tab-list" i]','[class*="tabbed" i]','[class*="tabs" i]']); if (el) { layer='class'; conf='med'; } }
      break;

    case 'accordion': {
      const det = document.querySelector('details');
      if (visible(det)) { el = sectionAncestor(det); layer='semantic'; conf='high'; }
      if (!el && document.querySelectorAll('[aria-expanded]').length >= 2) {
        const ax = firstVisible(['[aria-expanded]']); if (ax) { el = sectionAncestor(ax); layer='aria'; conf='high'; }
      }
      if (!el) { el = headingScan(['frequently asked','common questions','faqs','faq','questions','any questions']); if (el) { layer='heading'; conf='med'; } }
      if (!el) { el = firstVisible(['[class*="accordion" i]','[class*="faq" i]','[class*="collapse" i]']); if (el) { layer='class'; conf='med'; } }
      break;
    }

    case 'testimonials':
      el = headingScan(['what our customers','what our clients','what customers say',"don't just take",'testimonial','loved by','hear from our','our customers say','customer stories','rated','what people say','trusted by thousands']);
      if (el) { layer='heading'; conf='high'; }
      if (!el) { const bq = document.querySelector('blockquote'); if (visible(bq)) { el = sectionAncestor(bq); layer='semantic'; conf='med'; } }
      if (!el) { el = firstVisible(['[class*="testimonial" i]','[class*="review" i]','[class*="quote" i]','[class*="social-proof" i]']); if (el) { layer='class'; conf='med'; } }
      break;

    case 'trustbar':
      el = headingScan(['trusted by','powered by','as seen in','backed by','join thousands','companies that','used by','our customers include']);
      if (el) { layer='heading'; conf='med'; }
      if (!el) { el = firstVisible(['[class*="trust" i]','[class*="logo-bar" i]','[class*="logobar" i]','[class*="logos" i]','[class*="marquee" i]','[class*="partner" i]']); if (el) { layer='class'; conf='med'; } }
      break;

    case 'conversion-panel':
      el = headingScan(['ready to','get started','start your','start building',"let's talk",'book a demo','request a demo','get a demo','sign up','try it free','start free','get started for free','start now']);
      if (el) { layer='heading'; conf='med'; }
      if (!el) { el = firstVisible(['[class*="cta" i]','[class*="conversion" i]','[class*="call-to-action" i]','[class*="get-started" i]','[class*="final-cta" i]']); if (el) { layer='class'; conf='low'; } }
      break;

    case 'icon-card-deck':
      el = deckScan(3, false);
      if (el) { layer='geometry'; conf='med'; }
      if (!el) { el = firstVisible(['[class*="icon-card" i]','[class*="feature-card" i]','[class*="features" i]','[class*="benefits" i]']); if (el) { layer='class'; conf='low'; } }
      break;

    case 'image-card-deck':
      el = deckScan(3, true);
      if (el) { layer='geometry'; conf='med'; }
      if (!el) { el = firstVisible(['[class*="image-card" i]','[class*="blog" i]','[class*="resource" i]','[class*="card-grid" i]','[class*="post-grid" i]']); if (el) { layer='class'; conf='low'; } }
      break;

    case 'switchback':
      el = switchbackScan();
      if (el) { layer='geometry'; conf='med'; }
      if (!el) { el = firstVisible(['[class*="switchback" i]','[class*="alternating" i]','[class*="feature-row" i]','[class*="media-text" i]','[class*="split-section" i]']); if (el) { layer='class'; conf='low'; } }
      break;

    case 'heading-block':
      el = firstVisible(['[class*="heading-block" i]','[class*="section-header" i]','[class*="section-title" i]','[class*="page-header" i]']);
      if (el) { layer='class'; conf='low'; }
      break;

    case 'timed-switcher':
      el = firstVisible(['[class*="carousel" i]','[class*="slider" i]','[class*="swiper" i]','[class*="rotating" i]']);
      if (el) { el = sectionAncestor(el); layer='class'; conf='med'; }
      break;

    case 'mega-menu':
      el = firstVisible(['[class*="mega-menu" i]','[class*="megamenu" i]','nav [class*="dropdown" i]']);
      if (el) { layer='class'; conf='low'; }
      break;

    case 'dropdown-menu':
      el = firstVisible(['nav [class*="dropdown" i]','[class*="dropdown-menu" i]','[aria-haspopup="true"]']);
      if (el) { layer='class'; conf='low'; }
      break;

    case 'case-study':
      el = headingScan(['case study','case studies','success story','customer story','customer success','the results','their results']);
      if (el) { layer='heading'; conf='med'; }
      if (!el) { el = firstVisible(['[class*="case-study" i]','[class*="casestudy" i]','[class*="success-story" i]']); if (el) { layer='class'; conf='low'; } }
      break;

    case 'search':
      el = firstVisible(['[role="search"]']);
      if (el) { el = sectionAncestor(el); layer='aria'; conf='high'; }
      if (!el) { el = firstVisible(['[class*="search-results" i]','[class*="search-experience" i]','[class*="search" i]']); if (el) { layer='class'; conf='low'; } }
      break;
  }

  if (visible(el)) return mark(el, layer, conf);
  return {found:false};
}
"""


# ─── Image helper ─────────────────────────────────────────────────────────────

def to_jpeg(png_bytes: bytes, max_height: int = 1400) -> bytes:
    with Image.open(BytesIO(png_bytes)) as im:
        im = im.convert("RGB")
        if im.width > TARGET_WIDTH:
            ratio = TARGET_WIDTH / im.width
            im = im.resize((TARGET_WIDTH, int(im.height * ratio)), Image.LANCZOS)
        if im.height > max_height:
            im = im.crop((0, 0, im.width, max_height))
        buf = BytesIO()
        im.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        return buf.getvalue()


# ─── Page load ────────────────────────────────────────────────────────────────

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


def _positional_shot(page, where: str) -> bytes:
    if where == "bottom":
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.4)
    else:
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.2)
    return page.screenshot(full_page=False, type="png")


# ─── Vision backstop ──────────────────────────────────────────────────────────

def _resize_for_vision(png_bytes: bytes, width: int = 768) -> bytes:
    """Downscale a (possibly very tall) full-page PNG to keep the API payload small."""
    with Image.open(BytesIO(png_bytes)) as im:
        im = im.convert("RGB")
        if im.width > width:
            ratio = width / im.width
            im = im.resize((width, int(im.height * ratio)), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue()


def _crop_fraction(png_bytes: bytes, top_frac: float, bottom_frac: float) -> bytes:
    """Crop a full-page PNG to a vertical band [top_frac, bottom_frac] of its height."""
    with Image.open(BytesIO(png_bytes)) as im:
        H = im.height
        top = max(0, int(top_frac * H))
        bot = min(H, int(bottom_frac * H))
        if bot - top < 40:
            bot = min(H, top + 40)
        cropped = im.crop((0, top, im.width, bot))
        buf = BytesIO()
        cropped.save(buf, "PNG")
        return buf.getvalue()


def vision_locate(full_png: bytes, schema_name: str):
    """
    Ask Claude for the vertical bounds of the target section in a full-page
    screenshot. Returns (top_frac, bottom_frac) in 0..1, or None.
    """
    if not VISION_API_KEY:
        return None
    small = _resize_for_vision(full_png)
    b64 = base64.standard_b64encode(small).decode()
    prompt = (
        f"This is a full-page screenshot of a marketing website, top to bottom. "
        f"Find the FIRST clear \"{schema_name}\" section. "
        f"Reply with ONLY compact JSON, no prose: "
        f'{{"found": true_or_false, "top": <0..1>, "bottom": <0..1>}} '
        f"where top and bottom are fractions of the TOTAL image height marking that "
        f"section's vertical bounds. If the page has no such section, return "
        f'{{"found": false}}. Keep the band tight to the section.'
    )
    body = {
        "model": VISION_MODEL,
        "max_tokens": 150,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": VISION_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        obj = json.loads(m.group(0))
        if not obj.get("found"):
            return None
        top = max(0.0, min(1.0, float(obj.get("top", 0))))
        bot = max(0.0, min(1.0, float(obj.get("bottom", 1))))
        if bot - top < 0.02:
            return None
        return (top, bot)
    except Exception:
        return None


def capture(playwright, url: str, slug: str, timeout_ms: int):
    """
    Returns (png_bytes, layer, confidence) or (None, 'missed', None) when a hard
    component matches nothing and no fallback (positional or vision) applies.
    """
    browser, ctx, page = _load_page(playwright, url, timeout_ms)
    try:
        try:
            res = page.evaluate(DETECT_JS, slug)
        except Exception:
            res = {"found": False}

        if res.get("found"):
            loc = page.locator('[data-wsdetect="1"]').first
            try:
                loc.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.3)
                if res.get("h", 0) <= MAX_ELEM_H:
                    png = loc.screenshot(type="png", timeout=6000)
                else:
                    png = page.screenshot(full_page=False, type="png")  # too tall → viewport slice
                return png, res.get("layer", "?"), res.get("confidence", "?")
            except Exception:
                pass  # fall through to positional / vision / missed

        # No element (or element screenshot failed) → positional fallback if safe
        if slug in POSITIONAL_FALLBACK:
            return _positional_shot(page, POSITIONAL_FALLBACK[slug]), "positional", "low"

        # Vision backstop for static-but-mislocated components
        if VISION_ENABLED and slug in VISION_COMPONENTS:
            try:
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.2)
                full = page.screenshot(full_page=True, type="png", timeout=15000)
                bounds = vision_locate(full, SLUG_MAP[slug])
                if bounds:
                    return _crop_fraction(full, *bounds), "vision", "med"
            except Exception:
                pass

        return None, "missed", None
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
            png, layer, conf = capture(p, entry["url"], slug, args.timeout)
    except Exception as e:
        return {"status": "failed", "error": repr(e)}

    if png is None:
        return {"status": "missed", "layer": layer}

    jpg = to_jpeg(png)
    if not args.dry_run:
        out_path.write_bytes(jpg)
    return {"status": "ok", "bytes": len(jpg), "layer": layer, "confidence": conf}


# ─── Main ─────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="Capture section-specific screenshots (layered detection)")
    ap.add_argument("--component",   help="Component slug (e.g. hero, switchback). Omit for all.")
    ap.add_argument("--only",        help="Comma-separated entry IDs")
    ap.add_argument("--limit",       type=int, default=0)
    ap.add_argument("--redo",        action="store_true")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--timeout",     type=int, default=28000)
    ap.add_argument("--dry-run",     action="store_true")
    ap.add_argument("--vision",      action="store_true",
                    help="Use Claude vision as a backstop on DOM misses for static "
                         "components (" + ", ".join(sorted(VISION_COMPONENTS)) + "). "
                         "Needs ANTHROPIC_API_KEY in env or scripts/.env.")
    ap.add_argument("--vision-model", help="Override the vision model (default claude-sonnet-4-5)")
    return ap.parse_args()


def _load_anthropic_key() -> str:
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY") and "=" in line:
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return key


def _load_anthropic_model() -> str:
    import os
    return os.environ.get("ANTHROPIC_MODEL", "").strip() or "claude-sonnet-4-5"


def main():
    global VISION_API_KEY, VISION_MODEL, VISION_ENABLED
    args = parse_args()
    data = json.loads(JSON_PATH.read_text())
    only = set(s.strip() for s in args.only.split(",")) if args.only else None

    if args.vision:
        VISION_API_KEY = _load_anthropic_key()
        VISION_MODEL   = args.vision_model or _load_anthropic_model()
        if not VISION_API_KEY:
            sys.exit("--vision needs an API key.\n"
                     "  Add ANTHROPIC_API_KEY=sk-ant-... to scripts/.env (or export it).")
        VISION_ENABLED = True
        print(f"Vision backstop ON · model={VISION_MODEL} · components={', '.join(sorted(VISION_COMPONENTS))}")

    if args.component:
        slug = args.component.lower().strip()
        if slug not in SLUG_MAP:
            sys.exit(f"Unknown slug '{slug}'.\nKnown: {', '.join(sorted(SLUG_MAP))}")
        slugs = [slug]
    else:
        slugs = list(SLUG_MAP.keys())

    now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report = {"ranAt": now_ts, "dryRun": args.dry_run, "components": {}}
    grand = Counter()

    for slug in slugs:
        schema_name = SLUG_MAP[slug]
        targets = [
            e for e in data["entries"]
            if schema_name in (e.get("standoutElements") or {}).get("Components", [])
            and e.get("url")
            and (only is None or e["id"] in only)
        ]
        if args.limit:
            targets = targets[: args.limit]
        if not targets:
            print(f"[{slug}] no tagged entries — skipping")
            continue

        out_dir = SHOTS_DIR / slug
        if not args.dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        dry = " [DRY RUN]" if args.dry_run else ""
        print(f"\n=== {schema_name} ({slug}) — {len(targets)} entries{dry} ===")

        layer_counts = Counter()
        conf_counts  = Counter()
        stat = Counter()
        done = 0

        def worker(e):
            return e, process_entry(e, slug, out_dir, args)

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
                stat[s] += 1
                if s == "ok":
                    layer_counts[res["layer"]] += 1
                    conf_counts[res["confidence"]] += 1
                    print(f"  [{done:>4}/{len(targets)}] ✓ {res['layer']:<10} {res.get('confidence',''):<4} {entry['name'][:34]:34} {res['bytes']//1024}KB")
                elif s == "missed":
                    print(f"  [{done:>4}/{len(targets)}] – missed     {entry['name'][:34]:34} (no match — UI shows full-page)")
                elif s == "skipped":
                    pass
                else:
                    print(f"  [{done:>4}/{len(targets)}] ✗ failed     {entry['name'][:34]:34} {res.get('error','?')[:50]}")

        captured = stat["ok"]
        cov = (captured / len(targets) * 100) if targets else 0
        print(f"  → {captured}/{len(targets)} captured ({cov:.0f}% coverage)"
              f"  ·  missed {stat['missed']}  skipped {stat['skipped']}  failed {stat['failed']}")
        if layer_counts:
            print("    by layer:  " + "  ".join(f"{k}={v}" for k, v in layer_counts.most_common()))
        if conf_counts:
            print("    by conf:   " + "  ".join(f"{k}={v}" for k, v in conf_counts.most_common()))

        report["components"][slug] = {
            "schemaName": schema_name,
            "tagged": len(targets),
            "captured": captured,
            "coveragePct": round(cov, 1),
            "missed": stat["missed"],
            "failed": stat["failed"],
            "skipped": stat["skipped"],
            "byLayer": dict(layer_counts),
            "byConfidence": dict(conf_counts),
        }
        grand["tagged"] += len(targets); grand["captured"] += captured
        grand["missed"] += stat["missed"]; grand["failed"] += stat["failed"]; grand["skipped"] += stat["skipped"]

    report["totals"] = dict(grand)
    if not args.dry_run or True:  # always write the report (cheap, useful even on dry runs)
        REPORT_PATH.write_text(json.dumps(report, indent=2))

    print(f"\n{'─'*56}")
    tot_cov = (grand['captured'] / grand['tagged'] * 100) if grand['tagged'] else 0
    print(f"TOTAL: {grand['captured']}/{grand['tagged']} captured ({tot_cov:.0f}%)  ·  "
          f"missed {grand['missed']}  skipped {grand['skipped']}  failed {grand['failed']}")
    print(f"Report: {REPORT_PATH.relative_to(ROOT)}")
    if args.dry_run:
        print("[DRY RUN] No image files written.")


if __name__ == "__main__":
    main()
