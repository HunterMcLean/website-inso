#!/usr/bin/env python3
"""
Apply a patched inspiration.json downloaded from the in-page editor.

Reads from ~/Downloads/inspiration.json (or a path you pass), validates it,
overwrites data/inspiration.json, regenerates data/inspiration.js, and prints
a diff summary so you can sanity-check before deploying.

Usage:
    python3 scripts/apply_edits.py
    python3 scripts/apply_edits.py /path/to/downloaded.json
    python3 scripts/apply_edits.py --keep   # don't delete the source after applying
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "data" / "inspiration.json"
JS_PATH = ROOT / "data" / "inspiration.js"
DEFAULT_DOWNLOAD = Path.home() / "Downloads" / "inspiration.json"


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default=None,
                    help="Path to downloaded inspiration.json. Default: ~/Downloads/inspiration.json")
    ap.add_argument("--keep", action="store_true",
                    help="Don't delete the source file after applying.")
    ap.add_argument("--no-backup", action="store_true",
                    help="Skip writing data/inspiration.json.bak before overwriting.")
    return ap.parse_args()


def load_json(path: Path):
    if not path.exists():
        sys.exit(f"ERROR: file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: invalid JSON in {path}: {e}")


def write_db(data):
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    js = "// Auto-generated. Same data as inspiration.json, exposed as window.INSPIRATION_DATA.\n"
    js += "window.INSPIRATION_DATA = " + json.dumps(data, indent=2, ensure_ascii=False) + ";\n"
    JS_PATH.write_text(js)


def diff_summary(old, new):
    by_id_old = {e["id"]: e for e in old.get("entries", [])}
    by_id_new = {e["id"]: e for e in new.get("entries", [])}
    added = sorted(set(by_id_new) - set(by_id_old))
    removed = sorted(set(by_id_old) - set(by_id_new))
    changed = []
    for eid in sorted(set(by_id_new) & set(by_id_old)):
        a = by_id_old[eid]; b = by_id_new[eid]
        # compare on the editable fields
        diffs = []
        for f in ("companyType", "companyIndustry", "designAesthetic",
                  "wordAssociations", "typefaces", "industryLeader", "unconventional"):
            if a.get(f) != b.get(f):
                diffs.append(f)
        if a.get("standoutElements") != b.get("standoutElements"):
            diffs.append("standoutElements")
        if diffs:
            changed.append((eid, a.get("name", eid), diffs))
    return added, removed, changed


def main():
    args = parse_args()
    src = Path(args.source) if args.source else DEFAULT_DOWNLOAD

    print(f"Source: {src}")
    new = load_json(src)
    if not isinstance(new, dict) or "entries" not in new:
        sys.exit("ERROR: source JSON missing 'entries' key — wrong file?")

    old = load_json(JSON_PATH)
    added, removed, changed = diff_summary(old, new)

    print(f"Current:  {len(old.get('entries', []))} entries")
    print(f"Patched:  {len(new.get('entries', []))} entries")
    print(f"Added:    {len(added)}")
    print(f"Removed:  {len(removed)}")
    print(f"Changed:  {len(changed)}")
    if changed:
        print("\nChanged entries:")
        for eid, name, fields in changed[:25]:
            print(f"  {name[:30]:30}  {', '.join(fields)}")
        if len(changed) > 25:
            print(f"  …and {len(changed) - 25} more")
    if added:
        print("\nAdded entries:")
        for eid in added[:10]:
            print(f"  + {eid}")
    if removed:
        print("\nRemoved entries:")
        for eid in removed[:10]:
            print(f"  - {eid}")

    # Backup
    if not args.no_backup and JSON_PATH.exists():
        bak = JSON_PATH.with_suffix(".json.bak")
        shutil.copy2(JSON_PATH, bak)
        print(f"\nBackup: {bak.relative_to(ROOT)}")

    # Apply
    write_db(new)
    print(f"Wrote: data/inspiration.json + data/inspiration.js")

    # Tidy
    if not args.keep:
        try:
            src.unlink()
            print(f"Deleted source: {src}")
        except OSError as e:
            print(f"Couldn't delete source ({e}); leaving in place.")

    print("\nNext: ./scripts/deploy.sh")


if __name__ == "__main__":
    main()
