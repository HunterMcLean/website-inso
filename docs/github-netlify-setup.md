# GitHub + Netlify live-save setup

One-time setup so the in-page editor can save changes that go live in ~30s. After this you'll never run `apply_edits.py` or `deploy.sh` again — saves happen via the editor's "Save changes" button.

Architecture: editor → Netlify Function → commit to GitHub → push triggers Netlify rebuild → live.

## Step 1 — Create the GitHub repo

1. Go to [github.com/new](https://github.com/new).
2. Name it `web-inspo-library` (or whatever you like — note it for step 4).
3. **Private** is fine. Don't initialize with README/license/.gitignore (we already have those).
4. Click "Create repository". Don't push anything yet.

## Step 2 — Push the project to GitHub from your Mac

```sh
cd /Users/hmclean/Claudey/web-inspo-library

# Initialize if not already a git repo
git init -b main

# Stage + commit
git add -A
git commit -m "Initial commit: web inspo library"

# Add the remote (replace OWNER/REPO with what you used in step 1)
git remote add origin https://github.com/OWNER/REPO.git

# Push
git push -u origin main
```

If you've never authenticated to GitHub from the CLI before, you'll get prompted. The path of least resistance: install [GitHub CLI](https://cli.github.com/) and run `gh auth login`, which handles credentials automatically. Otherwise you'll be asked for a username + a Personal Access Token (NOT your password — generate a fine-grained PAT at [github.com/settings/tokens](https://github.com/settings/tokens) with `contents:read` on this repo).

## Step 3 — Generate a GitHub PAT for the save function

The save function needs its own token to commit. **This must be a different PAT from the one you use to push from your Mac** (different scopes, different lifecycle).

1. Visit [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new) (Fine-grained tokens).
2. **Token name**: `web-inspo-editor-save`
3. **Resource owner**: your GitHub username
4. **Repository access**: "Only select repositories" → choose your `web-inspo-library` repo
5. **Permissions** → Repository permissions:
   - **Contents**: Read and write
6. Generate. Copy the token (starts with `github_pat_…`).

## Step 4 — Connect Netlify to the GitHub repo

This replaces the current zip-deploy flow.

1. Go to your Netlify site → **Site configuration** → **Build & deploy** → **Continuous deployment**.
2. Click **Link site to Git** (or **Configure repository**).
3. Authenticate Netlify with GitHub if prompted, grant access to the new repo.
4. Pick the `web-inspo-library` repo, branch `main`.
5. Build settings (Netlify will read `netlify.toml`, but verify):
   - **Build command**: `node scripts/build-inspiration-js.js`
   - **Publish directory**: `.`
   - **Functions directory**: `netlify/functions` (auto-detected)
6. Save. Netlify will trigger an initial build.

## Step 5 — Set Netlify environment variables

Site → **Site configuration** → **Environment variables** → **Add variable**. Add these five:

| Key             | Value                                                 |
| --------------- | ----------------------------------------------------- |
| `EDIT_SECRET`   | A long random string. This is the editor's password.  |
| `GITHUB_TOKEN`  | The PAT from step 3 (`github_pat_…`)                  |
| `GITHUB_OWNER`  | Your GitHub username (e.g. `hmclean`)                 |
| `GITHUB_REPO`  | `web-inspo-library`                                   |
| `GITHUB_BRANCH` | `main` (optional — defaults to `main`)                |

Generate `EDIT_SECRET` however you like. Long random:

```sh
openssl rand -hex 24
```

Copy the value before saving — you'll paste it into your browser in the next step.

After adding, click **Trigger deploy** → **Clear cache and deploy site** so the function picks up the new env vars.

## Step 6 — Activate the editor in your browser

Visit:

```
https://webstacks-inspolibrary.netlify.app/?edit=PASTE_EDIT_SECRET_HERE
```

The page strips the `?edit=` param from the URL after reading it and stores the token in `localStorage`. From now on, every visit to that URL in that browser shows the **Browse / Edit** toggle and can save.

To deauthorize a browser later: visit `?edit=off` — that clears the stored token.

## Step 7 — Test the loop

1. Open the live site in the same browser.
2. Click **Edit**.
3. Change one entry's tags.
4. Hit **Save changes** in the floating bar.
5. You should see a toast: *"Saved. Netlify is rebuilding (~30s)."* with a link to the commit on GitHub.
6. Wait ~30s, hard-refresh the page, your edits are live.

## Troubleshooting

- **"Invalid edit token"**: the token in your browser doesn't match `EDIT_SECRET`. Re-run step 6 with the correct value.
- **"GitHub PUT failed (403)"**: PAT doesn't have `Contents: Read and write` on this repo, or the token expired.
- **"GitHub PUT failed (409)"**: rare, race condition (two saves at once). Retry the save.
- **Function not found / 404 at `/.netlify/functions/save-inspiration`**: the deploy didn't pick up the function. Ensure the file is at exactly `netlify/functions/save-inspiration.js` and that Netlify has redeployed since you connected the GitHub repo.
- **Build fails on Netlify**: check the build log for `build-inspiration-js: …`. Most common cause: malformed `data/inspiration.json` (e.g. trailing comma). Validate locally with `python3 -m json.tool data/inspiration.json`.
- **Saves succeed but page doesn't update**: hard-refresh (Cmd-Shift-R). The data files are served with `Cache-Control: no-cache` but a previously-cached copy may linger on first reload.

## What about the Submit-a-URL form?

Unchanged. Designers submitting via the in-site form still flow through Netlify Forms (no GitHub commit). Process those via `scripts/pull_submissions.py` like before.

## What if I want to roll back?

The save function only ever commits to `main`. Every save is a separate commit. Roll back to any earlier state via `git revert` or by deleting commits — Netlify will rebuild from the new HEAD.
