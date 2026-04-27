#!/usr/bin/env python3
"""
Pull recent submissions from the `submit-url` Netlify Form.

Tracks which submissions have already been processed in a local state file
(data/_submissions_state.json) so each run only emits NEW submissions.

Run from the project root on your Mac (sandbox can't reach api.netlify.com):

    python3 scripts/pull_submissions.py

Outputs JSON lines for each new submission — paste them into Cowork chat
and Claude will create review tasks. Use --all to dump every submission
(re-emits already-seen ones, doesn't update state).

Usage:
    python3 scripts/pull_submissions.py             # new submissions only, updates state
    python3 scripts/pull_submissions.py --all       # all submissions, no state update
    python3 scripts/pull_submissions.py --reset     # clear state (treat all as new)
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "scripts" / ".env"
STATE_PATH = ROOT / "data" / "_submissions_state.json"

API = "https://api.netlify.com/api/v1"
FORM_NAME = "submit-url"


def load_env():
    """Minimal .env parser (no external dependency)."""
    env = dict(os.environ)
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def api_get(path: str, token: str):
    req = urllib.request.Request(f"{API}{path}",
                                 headers={"Authorization": f"Bearer {token}",
                                          "User-Agent": "web-inspo-library/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Netlify API error {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error reaching Netlify: {e}")


def resolve_site_id(env, token):
    if env.get("NETLIFY_SITE_ID"):
        return env["NETLIFY_SITE_ID"]
    site_name = env.get("NETLIFY_SITE_NAME", "whimsical-cupcake-98eda4")
    sites = api_get(f"/sites?name={site_name}", token)
    if not sites:
        sys.exit(f"No site found with name '{site_name}'")
    return sites[0]["id"]


def normalize(sub):
    """Pull the user-facing fields out of the Netlify submission shape."""
    data = sub.get("data") or {}
    return {
        "submission_id": sub.get("id"),
        "created_at": sub.get("created_at"),
        "site_url": (data.get("site_url") or "").strip(),
        "site_name": (data.get("site_name") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
        "submitter": (data.get("submitter") or "").strip(),
        "netlify_admin_url": sub.get("site_url") or "",
    }


def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"seen": []}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Dump all submissions, don't update state.")
    ap.add_argument("--reset", action="store_true", help="Clear state file (treat all as new).")
    args = ap.parse_args()

    env = load_env()
    token = env.get("NETLIFY_AUTH_TOKEN")
    if not token:
        sys.exit("ERROR: NETLIFY_AUTH_TOKEN not set in scripts/.env")

    site_id = resolve_site_id(env, token)

    # Fetch all submissions for this site, filter to our form
    subs = api_get(f"/sites/{site_id}/submissions?per_page=100", token)
    subs = [s for s in subs if (s.get("form_name") == FORM_NAME)]

    if args.reset:
        save_state({"seen": []})

    state = load_state()
    seen = set(state.get("seen", []))

    if args.all:
        target = subs
    else:
        target = [s for s in subs if s.get("id") not in seen]

    payload = [normalize(s) for s in target]

    if not payload:
        sys.stderr.write(f"No new submissions (total in form: {len(subs)}).\n")
        return

    # JSON output (paste into Cowork chat → Claude creates review tasks)
    print(json.dumps(payload, indent=2))

    if not args.all:
        state["seen"] = [s.get("id") for s in subs]
        save_state(state)
        sys.stderr.write(f"\n→ {len(payload)} new submission(s). State updated.\n")


if __name__ == "__main__":
    main()
