# Pipeline Efficiency: Storage Cleanup & Dedup

## Context

The daily scrape pipeline (`scrape.yml`) uploads HTML to Supabase Storage (`raw-listings/{date}/{hash}.html`) but never deletes files. The extractor (`extract_run.py`) re-lists ALL folders and ALL files on every run to find unextracted ones, making `1 + N_folders + ceil(M_files/200)` Supabase API calls that grow unboundedly over time.

Additionally:
- Crash-induced duplicates (same hash in multiple date folders) waste storage.
- The `storage.list()` calls silently truncate at 1000 items — no pagination.

## Changes (ordered by implementation sequence)

### 1. Paginated storage listing

**File:** `backend/scraper/extract_run.py`

Add a `_list_all(bucket, path)` helper that loops with `offset` + `limit=1000` until a page returns <1000 items. Replace the two `storage.list()` calls (lines 66 and 72-73) with it.

**Why:** Prevents silent data loss when >1000 folders or >1000 files per folder exist.

### 2. Clean up storage in `get_unextracted_files()`

**File:** `backend/scraper/extract_run.py` — lines 91-97

Expand the existing dedup loop to collect paths to delete:
- Files whose hash is in `done` (already extracted — clears historical backlog)
- Duplicate files across folders (same hash, keep first, delete rest)

Batch-delete via `storage.remove(paths)` in chunks of 100. Best-effort — failures are logged and retried on next run.

### 3. Delete files after extraction in `run()`

**File:** `backend/scraper/extract_run.py` — `run()` function

Build a `hash_to_path` map from `pending` before the download loop. After extraction completes, delete storage files for:
- Successfully written listings (after `write_listing`)
- Pre-filtered non-enfermeria listings (during download loop, collect their paths)
- Post-filtered non-enfermeria listings (during results loop)

Per-hash deletion after `write_listing` is crash-safe: if the process dies mid-loop, unwritten files stay in storage for next run.

### 4. Move `mark_seen` into per-URL calls

**File:** `backend/scraper/run.py` — line 74

Move `mark_seen([url])` into the loop body right after `uploaded.append(url)` (line 65). Remove the batch call at line 74.

**Why:** Reduces the crash window for duplicate uploads from "entire run" to "one URL". Overhead is negligible since there's already a 1-2.5s sleep per URL in the loop.

## Files to modify

- `backend/scraper/extract_run.py` — changes 1, 2, 3
- `backend/scraper/run.py` — change 4
- `backend/tests/test_extract_logic.py` — update/add tests for pagination, cleanup, dedup deletion

## Verification

1. Run `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/ -v` — all tests pass
2. Trigger pipeline manually via `workflow_dispatch` and verify:
   - Logs show paginated listing (no silent truncation)
   - Logs show storage cleanup messages for duplicates/extracted files
   - After run, `raw-listings` bucket only contains truly unprocessed files
