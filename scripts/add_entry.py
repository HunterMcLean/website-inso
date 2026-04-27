#!/usr/bin/env python3
"""
Add a new entry to data/inspiration.json.

Two modes:

1) JSON-on-stdin (preferred when Claude appends programmatically):
     cat new_entry.json | python scripts/add_entry.py

2) CLI flags for quick manual additions:
     python scripts/add_entry.py \\
       --name "Acme" --url "https://acme.com" \\
       --industry "FinTech,B2B" \\
       --aesthetic "Minimalist,Dark Mode" \\
       --words "Modern,Trendy" \\
       --industry-leader

To read JSON from stdin, pass --from-stdin (avoids ambiguity when run from
non-interactive shells where stdin is a pipe but empty).

The script validates against schema.json, preserves Notion-only "extra" values,
and refuses duplicate URLs unless --replace is passed.
"""
import argparse, json, os, re, sys
from datetime import datetime
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "inspiration.json")
DATA_JS = os.path.join(ROOT, "data", "inspiration.js")
SCHEMA = os.path.join(ROOT, "data", "schema.json")

def slugify(s):
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")

def domain(u):
    p = urlparse(u if u.startswith("http") else "https://"+u)
    return p.netloc.replace("www.","")

def split_csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]

def load():
    with open(DATA) as f: return json.load(f)
def save(d):
    with open(DATA, "w") as f: json.dump(d, f, indent=2, ensure_ascii=False)
    # Keep the file:// shim in sync so double-clicking index.html still works.
    with open(DATA_JS, "w") as f:
        f.write("window.INSPIRATION_DATA = ")
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write(";\n")

def keep_canonical(values, canonical_set):
    """Drop any values not in canonical. Hunter wants doc-only taxonomy."""
    return [v for v in values if v in canonical_set]

def make_entry(args, schema):
    industries = split_csv(args.industry)
    company_type = [v for v in industries if v in schema["companyType"]]
    rest = [v for v in industries if v not in schema["companyType"]]
    canon_industry = keep_canonical(rest, set(schema["companyIndustry"]))
    canon_aesthetic = keep_canonical(split_csv(args.aesthetic), set(schema["designAesthetic"]))
    canon_words = keep_canonical(split_csv(args.words), set(schema["wordAssociations"]))

    standout = {k: [] for k in schema["standoutElements"].keys()}
    if args.standout:
        for v in split_csv(args.standout):
            for sub, opts in schema["standoutElements"].items():
                if v in opts:
                    standout[sub].append(v); break

    return {
        "id": slugify(args.name) + "-" + slugify(domain(args.url) or "site"),
        "name": args.name,
        "url": args.url,
        "domain": domain(args.url),
        "screenshot": args.screenshot,
        "companyType": company_type,
        "companyIndustry": canon_industry,
        "siteStructure": [],  # field retained but no longer surfaced in UI
        "designAesthetic": canon_aesthetic,
        "standoutElements": standout,
        "wordAssociations": canon_words,
        "industryLeader": bool(args.industry_leader),
        "unconventional": bool(args.unconventional),
        "typefaces": split_csv(args.typefaces),
        "createdAt": datetime.utcnow().strftime("%B %d, %Y %I:%M %p"),
        "source": "manual-add",
    }

def from_stdin(payload, schema):
    """Accept a partial dict; fill defaults; ensure schema-compliant shape."""
    p = dict(payload)
    p.setdefault("companyType", []); p.setdefault("companyIndustry", [])
    p.setdefault("siteStructure", []); p.setdefault("designAesthetic", [])
    p.setdefault("wordAssociations", []); p.setdefault("typefaces", [])
    p.setdefault("industryLeader", False); p.setdefault("unconventional", False)
    p["domain"] = p.get("domain") or domain(p["url"])
    p["id"] = p.get("id") or (slugify(p["name"]) + "-" + slugify(p["domain"] or "site"))
    if "standoutElements" not in p: p["standoutElements"] = {k: [] for k in schema["standoutElements"]}
    p.setdefault("createdAt", datetime.utcnow().strftime("%B %d, %Y %I:%M %p"))
    p.setdefault("source", "claude-add")
    p.setdefault("screenshot", None)
    # Drop any non-canonical values
    p["companyIndustry"] = keep_canonical(p["companyIndustry"], set(schema["companyIndustry"]))
    p["designAesthetic"] = keep_canonical(p["designAesthetic"], set(schema["designAesthetic"]))
    p["wordAssociations"] = keep_canonical(p["wordAssociations"], set(schema["wordAssociations"]))
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name"); ap.add_argument("--url")
    ap.add_argument("--industry", help="Comma-sep, can include B2B/B2C + industries")
    ap.add_argument("--aesthetic")
    ap.add_argument("--standout"); ap.add_argument("--words")
    ap.add_argument("--typefaces"); ap.add_argument("--screenshot")
    ap.add_argument("--industry-leader", action="store_true")
    ap.add_argument("--unconventional", action="store_true")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--from-stdin", action="store_true",
                    help="Read entry JSON from stdin (use when piping)")
    args = ap.parse_args()

    with open(SCHEMA) as f: schema = json.load(f)
    db = load()

    if args.from_stdin:
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit("--from-stdin set but no JSON received.")
        entry = from_stdin(json.loads(raw), schema)
    else:
        if not args.name or not args.url:
            sys.exit("Provide --name and --url, or use --from-stdin with piped JSON.")
        entry = make_entry(args, schema)

    # Dedup by URL
    existing_idx = next((i for i,e in enumerate(db["entries"]) if e["url"].rstrip("/") == entry["url"].rstrip("/")), None)
    if existing_idx is not None and not args.replace:
        sys.exit(f"Duplicate URL already in library: {entry['url']}. Use --replace to overwrite.")
    if existing_idx is not None:
        db["entries"][existing_idx] = entry
        action = "replaced"
    else:
        db["entries"].append(entry); action = "added"
    save(db)
    print(f"{action}: {entry['name']}  ({entry['url']})")
    print(f"Total entries: {len(db['entries'])}")

if __name__ == "__main__":
    main()
