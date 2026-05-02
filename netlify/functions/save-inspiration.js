// Netlify Function: accepts an edited inspiration.json from the in-page editor,
// validates a shared EDIT_SECRET, and commits the new file to GitHub via PAT.
// GitHub push triggers a fresh Netlify deploy (~30s).
//
// Env vars (set in Netlify dashboard → Site → Environment variables):
//   EDIT_SECRET    - shared token the editor must include in X-Edit-Token
//   GITHUB_TOKEN   - GitHub PAT with `contents:write` on the target repo
//   GITHUB_OWNER   - e.g. "hmclean"
//   GITHUB_REPO    - e.g. "web-inspo-library"
//   GITHUB_BRANCH  - default "main"
//
// The function commits ONLY data/inspiration.json. The Netlify build regenerates
// data/inspiration.js from it (see scripts/build-inspiration-js.js).

const PATH_TARGET = "data/inspiration.json";

function jsonResponse(status, obj) {
  return {
    statusCode: status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Edit-Token, X-Edit-Author",
    },
    body: JSON.stringify(obj),
  };
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return jsonResponse(204, {});

  // GET ?verify=1 — lightweight token check used by the lock-button UI
  if (event.httpMethod === "GET") {
    const expected = process.env.EDIT_SECRET;
    const headerToken = event.headers["x-edit-token"] || event.headers["X-Edit-Token"] || "";
    if (!expected) return jsonResponse(500, { error: "Server misconfig" });
    if (!headerToken || !timingSafeEqual(headerToken, expected)) return jsonResponse(401, { ok: false });
    return jsonResponse(200, { ok: true });
  }

  if (event.httpMethod !== "POST") {
    return jsonResponse(405, { error: "Method not allowed" });
  }

  // --- Validate edit token ---
  const expected = process.env.EDIT_SECRET;
  if (!expected) {
    return jsonResponse(500, { error: "Server misconfig: EDIT_SECRET not set" });
  }
  const headerToken =
    event.headers["x-edit-token"] ||
    event.headers["X-Edit-Token"] ||
    "";
  if (!headerToken || !timingSafeEqual(headerToken, expected)) {
    return jsonResponse(401, { error: "Invalid edit token" });
  }

  // --- Parse + validate payload ---
  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch (e) {
    return jsonResponse(400, { error: "Invalid JSON" });
  }
  if (
    !payload ||
    !Array.isArray(payload.entries) ||
    typeof payload.schema !== "object"
  ) {
    return jsonResponse(400, {
      error: "Payload must include `entries` array and `schema` object",
    });
  }
  if (payload.entries.length === 0) {
    return jsonResponse(400, { error: "Refusing to commit empty entries array" });
  }

  // --- GitHub config ---
  const ghToken = process.env.GITHUB_TOKEN;
  const ghOwner = process.env.GITHUB_OWNER;
  const ghRepo = process.env.GITHUB_REPO;
  const ghBranch = process.env.GITHUB_BRANCH || "main";
  if (!ghToken || !ghOwner || !ghRepo) {
    return jsonResponse(500, {
      error: "Server misconfig: GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO missing",
    });
  }

  const apiBase = `https://api.github.com/repos/${ghOwner}/${ghRepo}`;
  const ghHeaders = {
    Authorization: `Bearer ${ghToken}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "web-inspo-editor",
  };

  // --- 1. Get current SHA of the file ---
  const getUrl = `${apiBase}/contents/${PATH_TARGET}?ref=${encodeURIComponent(
    ghBranch,
  )}`;
  let sha;
  try {
    const r = await fetch(getUrl, { headers: ghHeaders });
    if (!r.ok) {
      const text = await r.text();
      return jsonResponse(502, {
        error: `GitHub GET failed (${r.status})`,
        detail: text.slice(0, 300),
      });
    }
    const meta = await r.json();
    sha = meta.sha;
  } catch (e) {
    return jsonResponse(502, { error: `GitHub GET threw: ${e.message}` });
  }

  // --- 2. PUT new content ---
  const newContent = JSON.stringify(payload, null, 2) + "\n";
  const b64 = Buffer.from(newContent, "utf-8").toString("base64");
  const author = String(
    event.headers["x-edit-author"] || event.headers["X-Edit-Author"] || "editor",
  ).slice(0, 60);
  const message = `editor: update ${payload.entries.length} entries (via ${author})`;

  let putData;
  try {
    const r = await fetch(`${apiBase}/contents/${PATH_TARGET}`, {
      method: "PUT",
      headers: { ...ghHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        content: b64,
        sha,
        branch: ghBranch,
      }),
    });
    if (!r.ok) {
      const text = await r.text();
      return jsonResponse(502, {
        error: `GitHub PUT failed (${r.status})`,
        detail: text.slice(0, 300),
      });
    }
    putData = await r.json();
  } catch (e) {
    return jsonResponse(502, { error: `GitHub PUT threw: ${e.message}` });
  }

  return jsonResponse(200, {
    ok: true,
    entries: payload.entries.length,
    commitSha: putData.commit?.sha || null,
    commitUrl: putData.commit?.html_url || null,
    branch: ghBranch,
    note: "Netlify is rebuilding from this commit. Live in ~30s.",
  });
};

// Constant-time string compare to dodge timing attacks on the token.
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}
