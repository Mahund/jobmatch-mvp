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
| Project | Root Directory | Purpose |
|---------|---------------|---------|
| jobmatch-mvp-api | `backend` | FastAPI backend |
| jobmatch-mvp-web | `frontend` | Next.js frontend |

Both root directories must be set in Vercel dashboard → Settings → General → Root Directory.

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

When the user says they merged a PR and want to start something new, follow this sequence before creating a new branch:
1. `git checkout master`
2. `git fetch origin`
3. `git status` — verify master is behind or up to date (not diverged)
4. `git pull origin master`
5. Only then proceed with the normal branch → commit → push → PR flow
