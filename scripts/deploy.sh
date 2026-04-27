#!/usr/bin/env bash
# Deploy the microsite to Netlify.
#
# Usage:
#   1. Copy scripts/.env.example → scripts/.env and fill in your values.
#   2. From the project root (web-inspo-microsite/), run: ./scripts/deploy.sh
#
# What it does:
#   - Loads scripts/.env (NETLIFY_AUTH_TOKEN required, NETLIFY_SITE_ID optional)
#   - If NETLIFY_SITE_ID is missing, resolves it from NETLIFY_SITE_NAME via the API
#   - Zips the deployable files (everything except scripts/, work/, hidden files)
#   - POSTs the zip to https://api.netlify.com/api/v1/sites/{site_id}/deploys
#   - Polls until the deploy is "ready", then prints the live URL.
set -euo pipefail

# --- Locate self + project root regardless of where it's invoked from ---
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# --- Load env ---
if [[ -f "$HERE/.env" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$HERE/.env"; set +a
fi

if [[ -z "${NETLIFY_AUTH_TOKEN:-}" ]]; then
  echo "ERROR: NETLIFY_AUTH_TOKEN not set."
  echo "  Copy scripts/.env.example → scripts/.env and add your token."
  exit 1
fi

NETLIFY_SITE_NAME="${NETLIFY_SITE_NAME:-whimsical-cupcake-98eda4}"

# --- Resolve site ID if not provided ---
if [[ -z "${NETLIFY_SITE_ID:-}" ]]; then
  echo "→ Resolving site ID for '$NETLIFY_SITE_NAME'..."
  RESP="$(curl -fsSL -H "Authorization: Bearer $NETLIFY_AUTH_TOKEN" \
    "https://api.netlify.com/api/v1/sites?name=$NETLIFY_SITE_NAME")"
  NETLIFY_SITE_ID="$(printf '%s' "$RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["id"]) if d else sys.exit("no site found")')"
  echo "  resolved: $NETLIFY_SITE_ID"
fi

# --- Build zip (exclude scripts, work, hidden files, OS junk) ---
ZIP="$(mktemp -u).zip"
echo "→ Building deploy zip..."
( cd "$ROOT" && zip -qr "$ZIP" . \
    -x "scripts/*" "work/*" ".*" "*/.*" "*.DS_Store" "**/__pycache__/*" "**/*.pyc" "scripts/.env" \
       "data/_*" "data/*-report.json" "data/figma-stubs-added.json" "data/inspiration.json.bak" )
echo "  zip: $(du -h "$ZIP" | cut -f1)"

# --- Upload deploy ---
echo "→ Uploading to Netlify..."
DEPLOY_JSON="$(curl -fsSL -X POST \
  -H "Authorization: Bearer $NETLIFY_AUTH_TOKEN" \
  -H "Content-Type: application/zip" \
  --data-binary "@$ZIP" \
  "https://api.netlify.com/api/v1/sites/$NETLIFY_SITE_ID/deploys")"

DEPLOY_ID="$(printf '%s' "$DEPLOY_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "  deploy id: $DEPLOY_ID"

# --- Poll until ready (or fail) ---
echo "→ Waiting for deploy to go live..."
for i in $(seq 1 60); do
  STATE_JSON="$(curl -fsSL -H "Authorization: Bearer $NETLIFY_AUTH_TOKEN" \
    "https://api.netlify.com/api/v1/sites/$NETLIFY_SITE_ID/deploys/$DEPLOY_ID")"
  STATE="$(printf '%s' "$STATE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')"
  case "$STATE" in
    ready)
      URL="$(printf '%s' "$STATE_JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("deploy_ssl_url") or d.get("ssl_url"))')"
      echo "✓ Deployed: $URL"
      rm -f "$ZIP"
      exit 0
      ;;
    error)
      echo "✗ Deploy failed."
      printf '%s\n' "$STATE_JSON" | python3 -m json.tool
      rm -f "$ZIP"
      exit 1
      ;;
    *)
      printf "  state=%s (%ds)\r" "$STATE" "$((i * 2))"
      sleep 2
      ;;
  esac
done

echo "✗ Timed out waiting for deploy."
rm -f "$ZIP"
exit 1
