"""
Step 3 orchestrator: Storage HTML → Claude Batch extraction → listings table.
Uses the Anthropic Message Batches API (50% cheaper, async-safe for nightly pipeline).
Run with:  python -m scraper.extract_run
"""
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.extract import build_batch_request_from_soup, submit_batch, poll_batch, iter_batch_results
from db.supabase_client import get_client


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def _parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _extract_title_from_soup(soup: BeautifulSoup) -> str | None:
    """Cheaply extract job title from a parsed listing without using Claude."""
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else None


def _is_enfermeria_role(title: str | None) -> bool:
    normalized_title = _normalize_text(title)
    if not normalized_title:
        return False

    # Keep only professional Enfermeria roles, explicitly excluding technical tracks.
    if "enfermer" not in normalized_title:
        return False

    excluded_markers = [
        "tens",
        "tecnico",
        "tecnica",
        "auxiliar",
        "paramedic",
        "kinesiolog",
        "estudiante",
        "intern",
    ]
    return not any(marker in normalized_title for marker in excluded_markers)


def get_unextracted_files() -> list[dict]:
    """
    List all files in Storage that don't yet have a row in listings.
    Returns list of {path, hash} dicts.
    """
    db = get_client()

    files = db.storage.from_("raw-listings").list(path="", options={"limit": 1000})

    all_files = []
    for item in files:
        if item.get("id") is None:
            folder = item["name"]
            folder_files = db.storage.from_("raw-listings").list(
                path=folder, options={"limit": 1000}
            )
            for f in folder_files:
                if f["name"].endswith(".html"):
                    hash_ = f["name"].replace(".html", "")
                    all_files.append({"path": f"{folder}/{f['name']}", "hash": hash_})

    if not all_files:
        return []

    hashes = [f["hash"] for f in all_files]
    done: set[str] = set()
    chunk_size = 200
    for i in range(0, len(hashes), chunk_size):
        chunk = hashes[i : i + chunk_size]
        result = db.table("listings").select("url_hash").in_("url_hash", chunk).execute()
        done.update(row["url_hash"] for row in result.data)

    seen: set[str] = set()
    unique: list[dict] = []
    for f in all_files:
        if f["hash"] not in done and f["hash"] not in seen:
            seen.add(f["hash"])
            unique.append(f)
    return unique


def download_html(path: str) -> str | None:
    db = get_client()
    try:
        data = db.storage.from_("raw-listings").download(path)
        return data.decode("utf-8")
    except Exception as e:
        print(f"    Download failed for {path}: {e}")
        return None


def get_urls_for_hashes(hashes: list[str]) -> dict[str, str]:
    db = get_client()
    url_map: dict[str, str] = {}
    chunk_size = 200
    for i in range(0, len(hashes), chunk_size):
        chunk = hashes[i : i + chunk_size]
        result = db.table("seen_urls").select("url_hash,url").in_("url_hash", chunk).execute()
        url_map.update({row["url_hash"]: row["url"] for row in result.data})
    return url_map


def write_listing(hash_: str, url: str, fields: dict) -> None:
    db = get_client()
    row = {
        "url_hash": hash_,
        "url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "extraction_status": "ok" if fields.get("confidence", 0) >= 0.6 else "low_confidence",
        **fields,
    }
    db.table("listings").upsert(row, on_conflict="url_hash").execute()


def run():
    print("=== JobMatch extractor — Step 3 (Batch API) ===")

    print("\n[1/4] Finding unextracted files in Storage...")
    pending = get_unextracted_files()
    print(f"  Pending: {len(pending)}")

    if not pending:
        print("  Nothing to extract. Exiting.")
        return

    print(f"\n[2/4] Downloading HTML for {len(pending)} listings...")
    requests = []
    skipped = 0
    skipped_non_enfermeria = 0
    for file in pending:
        html = download_html(file["path"])
        if html is None:
            skipped += 1
            continue
        soup = _parse_html(html)
        title_guess = _extract_title_from_soup(soup)
        if not _is_enfermeria_role(title_guess):
            print(f"  {title_guess or '(no title)'} — pre-filtered [non-enfermeria]")
            skipped_non_enfermeria += 1
            continue
        requests.append(build_batch_request_from_soup(file["hash"], soup))

    print(f"  Ready: {len(requests)}  Pre-filtered: {skipped_non_enfermeria}  Download failures: {skipped}")

    if not requests:
        print("  Nothing to submit. Exiting.")
        return

    print(f"\n[3/4] Submitting batch of {len(requests)} to Claude (50% off via Batch API)...")
    batch_id = submit_batch(requests)
    print(f"  Batch ID: {batch_id}")
    poll_batch(batch_id, poll_interval=30)

    print(f"\n[4/4] Processing results...")
    hashes = [r["custom_id"] for r in requests]
    url_map = get_urls_for_hashes(hashes)

    ok = low_conf = failed = skipped_post = 0
    for hash_, fields in iter_batch_results(batch_id):
        if fields is None:
            print(f"  {hash_}: extraction failed")
            failed += 1
            continue

        title = fields.get("title", "?")
        if not _is_enfermeria_role(title):
            print(f"  {title} — skipped post-extraction [non-enfermeria role]")
            skipped_post += 1
            continue

        url = url_map.get(hash_, f"unknown:{hash_}")
        conf = fields.get("confidence", 0)
        status = "ok" if conf >= 0.6 else "low_confidence"
        print(f"  {title} @ {fields.get('company', '?')} — conf={conf:.2f} [{status}]")

        try:
            write_listing(hash_, url, fields)
            if status == "ok":
                ok += 1
            else:
                low_conf += 1
        except Exception as e:
            print(f"    DB write failed: {e}")
            failed += 1

    print(
        f"\nDone. OK: {ok}  Low-confidence: {low_conf}  "
        f"Pre-filtered: {skipped_non_enfermeria}  Post-filtered: {skipped_post}  Failed: {failed}"
    )


if __name__ == "__main__":
    run()
