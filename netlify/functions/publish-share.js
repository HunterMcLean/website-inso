// Netlify Function: publishes/updates a "living" shared album.
// Writes data/shares/<id>.json to GitHub via PAT (same pattern as save-inspiration.js).
// The read path is a plain static fetch of /data/shares/<id>.json — no function needed.
//
// A living link has a STABLE url (?share=<id>): re-publishing overwrites the same
// file, so the external URL never changes but always shows the latest album state.
//
// Env vars (already set for save-inspiration): EDIT_SECRET, GITHUB_TOKEN,
// GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH.

const ID_RE = /^[a-z0-9]{6,16}$/;
const MAX_SITES = 2000;

function jsonResponse(status, obj) {
  return {
    statusCode: status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Edit-Token",
    },
    body: JSON.stringify(obj),
  };
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return result === 0;
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return jsonResponse(204, {});
  if (event.httpMethod !== "POST") return jsonResponse(405, { error: "Method not allowed" });

  // --- Auth ---
  const expected = process.env.EDIT_SECRET;
  if (!expected) return jsonResponse(500, { error: "Server misconfig: EDIT_SECRET not set" });
  const headerToken = event.headers["x-edit-token"] || event.headers["X-Edit-Token"] || "";
  if (!headerToken || !timingSafeEqual(headerToken, expected)) {
    return jsonResponse(401, { error: "Invalid edit token" });
  }

  // --- Parse + validate ---
  let payload;
  try { payload = JSON.parse(event.body || "{}"); }
  catch (e) { return jsonResponse(400, { error: "Invalid JSON" }); }

  const id = String(payload.id || "");
  if (!ID_RE.test(id)) return jsonResponse(400, { error: "Invalid share id" });
  if (typeof payload.name !== "string" || !payload.name.trim()) {
    return jsonResponse(400, { error: "Missing album name" });
  }
  if (!Array.isArray(payload.siteIds) || payload.siteIds.length === 0) {
    return jsonResponse(400, { error: "Album has no sites" });
  }
  if (payload.siteIds.length > MAX_SITES) {
    return jsonResponse(400, { error: "Album too large" });
  }

  const record = {
    id,
    name: payload.name.slice(0, 200),
    siteIds: payload.siteIds.map(String).slice(0, MAX_SITES),
    groups: Array.isArray(payload.groups) ? payload.groups.map(String) : [],
    siteGroups: (payload.siteGroups && typeof payload.siteGroups === "object") ? payload.siteGroups : {},
    updatedAt: new Date().toISOString(),
  };

  // --- GitHub config ---
  const ghToken = process.env.GITHUB_TOKEN;
  const ghOwner = process.env.GITHUB_OWNER;
  const ghRepo = process.env.GITHUB_REPO;
  const ghBranch = process.env.GITHUB_BRANCH || "main";
  if (!ghToken || !ghOwner || !ghRepo) {
    return jsonResponse(500, { error: "Server misconfig: GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO missing" });
  }
  const path = `data/shares/${id}.json`;
  const apiBase = `https://api.github.com/repos/${ghOwner}/${ghRepo}`;
  const ghHeaders = {
    Authorization: `Bearer ${ghToken}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "web-inspo-share",
  };

  // --- 1. Get current SHA if the file already exists (update); 404 → create ---
  let sha;
  try {
    const r = await fetch(`${apiBase}/contents/${path}?ref=${encodeURIComponent(ghBranch)}`, { headers: ghHeaders });
    if (r.ok) { sha = (await r.json()).sha; }
    else if (r.status !== 404) {
      return jsonResponse(502, { error: `GitHub GET failed (${r.status})`, detail: (await r.text()).slice(0, 300) });
    }
  } catch (e) {
    return jsonResponse(502, { error: `GitHub GET threw: ${e.message}` });
  }

  // --- 2. PUT content ---
  const content = Buffer.from(JSON.stringify(record, null, 2) + "\n", "utf-8").toString("base64");
  const message = `${sha ? "update" : "create"} living share: ${id}`;
  let putData;
  try {
    const body = { message, content, branch: ghBranch };
    if (sha) body.sha = sha;
    const r = await fetch(`${apiBase}/contents/${path}`, {
      method: "PUT",
      headers: { ...ghHeaders, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      return jsonResponse(502, { error: `GitHub PUT failed (${r.status})`, detail: (await r.text()).slice(0, 300) });
    }
    putData = await r.json();
  } catch (e) {
    return jsonResponse(502, { error: `GitHub PUT threw: ${e.message}` });
  }

  return jsonResponse(200, {
    ok: true,
    id,
    path,
    updated: !!sha,
    commitSha: putData.commit?.sha || null,
    note: "Netlify is rebuilding. Live in ~30s.",
  });
};
