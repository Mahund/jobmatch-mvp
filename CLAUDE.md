# JobMatch MVP — Claude Code Rules

## Deployment verification rule
Before setting any service URL as a target (env var, config, hardcoded), verify the service is actually live and responding:
```bash
curl -s <url>/health
```
Do not configure a service pointing to an undeployed or unverified URL.

## Project layout
- `backend/` — FastAPI app, deployed to Vercel project `jobmatch-mvp-api`
- `frontend/` — Next.js app, deployed to Vercel project `jobmatch-mvp-web`
- `.github/workflows/scrape.yml` — daily pipeline: scrape → extract → rematch
- `.github/workflows/ci.yml` — CI: runs on PRs and pushes to master
- `.github/pull_request_template.md` — PR checklist template

## CI checks
Triggered on every PR and push to `master`. Two required jobs:
- **Backend checks**: Python 3.12, compiles all backend code, runs `pytest backend/tests`
- **Frontend checks**: Node 20, `npm run lint`, `npm test`, `npm run build`

Backend tests use `PYTHONPATH=backend`. Frontend build uses placeholder env vars (no real Supabase/API needed in CI).

## Vercel projects
| Project | Project ID | Root Directory | Purpose |
|---------|-----------|---------------|---------|
| jobmatch-mvp-api | `prj_IGPSpUoul6e0WyxIHPsAKH2zsBAM` | `backend` | FastAPI backend |
| jobmatch-mvp-web | `prj_mTlQgg3YFf4FabNHjF4widNeKa6E` | `frontend` | Next.js frontend |

Team slug: `mahunds-projects` · Team ID: `team_MsubucdK6ygrE3nLj5UrXmNT`

Both root directories must be set in Vercel dashboard → Settings → General → Root Directory.

## Vercel CLI rules

**Never run `vercel` or `vercel deploy` from the repo root.** The CLI will detect multiple frameworks, create a new combined project, and modify/create `vercel.json` with `experimentalServices` — all of which corrupt the setup.

**Correct deploy commands:**
```bash
# Deploy backend
cd backend && npx vercel --prod --scope mahunds-projects --yes

# Deploy frontend
cd frontend && npx vercel --prod --scope mahunds-projects --yes
```

Each subdirectory has its own `.vercel/project.json` linking it to the correct project. Do not delete these.

**Setting env vars on a project** — use the REST API (avoid `vercel env add` which also requires the right linked directory):
```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/root/.local/share/com.vercel.cli/auth.json'))['token'])")
curl -s -X POST "https://api.vercel.com/v10/projects/<projectId>/env?teamId=team_MsubucdK6ygrE3nLj5UrXmNT" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"key":"VAR_NAME","value":"value","type":"plain","target":["production"]}'
```

**Triggering a redeploy** (pick up new env vars without a code change):
```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/root/.local/share/com.vercel.cli/auth.json'))['token'])")
# Get latest deployment ID first, then:
curl -s -X POST "https://api.vercel.com/v13/deployments?teamId=team_MsubucdK6ygrE3nLj5UrXmNT" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"<project-name>","project":"<projectId>","deploymentId":"<last-dpl-id>","target":"production"}'
```

**After any Vercel CLI session**, verify no new projects were accidentally created:
```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/root/.local/share/com.vercel.cli/auth.json'))['token'])")
curl -s "https://api.vercel.com/v9/projects?teamId=team_MsubucdK6ygrE3nLj5UrXmNT" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; [print(p['name'],p['id']) for p in json.load(sys.stdin)['projects']]"
```
Expected: only `jobmatch-mvp-api` and `jobmatch-mvp-web`.

## Environment variables
Backend needs: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `SUPABASE_JWT_SECRET`
Frontend needs: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`

## Infrastructure (already live)
- Supabase project: `ocqoqtoqawvcapktoojf` (sa-east-1)
- Tables: `listings`, `matches`, `profiles`, `seen_urls`
- Storage bucket: `raw-listings` (private)
- Auth: email+password, test user `test@jobmatch.dev`

## Python environment
- Venv at `.venv/` — always use `.venv/bin/python` and `.venv/bin/pip`
- Run backend modules from `backend/` directory: `python -m scraper.run`

## Supabase key format
The service key uses the newer `sb_secret_` format (not a JWT). Auth tokens use ES256 — validate via `db.auth.get_user(token)`, not manual JWT decode.

## Git / PR workflow
When pushing changes, always follow this sequence:
1. Create a new branch (e.g. `git checkout -b feat/short-description`)
2. Commit the changes
3. Push the branch (`git push -u origin <branch>`)
4. Create a PR with `gh pr create`
5. Wait 60 seconds, then check CI status with `gh pr checks <pr-number>`
6. Wait another 120 seconds, then check for unresolved Copilot review comments (see query below)
7. If there are unresolved comments, read each one, address it in code, commit, and push — then repeat from step 6 until no unresolved comments remain

To check unresolved PR review comments, use GraphQL (the REST API does not expose resolution status):
```bash
gh api graphql -f query='
{
  repository(owner: "Mahund", name: "jobmatch-mvp") {
    pullRequest(number: <PR>) {
      reviewThreads(first: 50) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes { path body }
          }
        }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads.nodes | {total: length, resolved: [.[] | select(.isResolved)] | length, unresolved: [.[] | select(.isResolved == false)] | length}'
```

To read the full text of unresolved comments (needed before addressing them):
```bash
gh api graphql -f query='
{
  repository(owner: "Mahund", name: "jobmatch-mvp") {
    pullRequest(number: <PR>) {
      reviewThreads(first: 50) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes { path body }
          }
        }
      }
    }
  }
}' --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | {path: .comments.nodes[0].path, comment: .comments.nodes[0].body}]'
```

When the user says they merged a PR and want to start something new, follow this sequence before creating a new branch:
1. `git checkout master`
2. `git fetch origin`
3. `git status` — verify master is behind or up to date (not diverged)
4. `git pull origin master`
5. Only then proceed with the normal branch → commit → push → PR flow
