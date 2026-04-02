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
