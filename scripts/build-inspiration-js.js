#!/usr/bin/env node
// Regenerate data/inspiration.js from data/inspiration.json.
// Runs as the Netlify build command and can also be run locally.

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const SRC = path.join(ROOT, "data", "inspiration.json");
const DST = path.join(ROOT, "data", "inspiration.js");

if (!fs.existsSync(SRC)) {
  console.error(`build-inspiration-js: source missing: ${SRC}`);
  process.exit(1);
}

const raw = fs.readFileSync(SRC, "utf-8");
let data;
try {
  data = JSON.parse(raw);
} catch (err) {
  console.error(`build-inspiration-js: invalid JSON in ${SRC}: ${err.message}`);
  process.exit(1);
}

const out =
  "// Auto-generated. Same data as inspiration.json, exposed as window.INSPIRATION_DATA.\n" +
  "window.INSPIRATION_DATA = " +
  JSON.stringify(data, null, 2) +
  ";\n";

fs.writeFileSync(DST, out);

const entries = Array.isArray(data?.entries) ? data.entries.length : "?";
console.log(`build-inspiration-js: wrote data/inspiration.js (${entries} entries)`);
