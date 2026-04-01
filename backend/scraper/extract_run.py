"""
Step 3 orchestrator: Storage HTML → Claude extraction → listings table.
Run with:  python -m scraper.extract_run
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.extract import extract_listing
from scraper.dedup import url_hash
from db.supabase_client import get_client


def get_unextracted_files() -> list[dict]:
    """
    List all files in Storage that don't yet have a row in listings.
    Returns list of {path, hash} dicts.
    """
    db = get_client()

    # List all files in raw-listings bucket
    files = db.storage.from_("raw-listings").list(
        path="",
        options={"limit": 1000}
    )

    all_files = []
    for item in files:
        # Each top-level item is a date folder
        if item.get("id") is None:
            folder = item["name"]
            folder_files = db.storage.from_("raw-listings").list(
                path=folder,
                options={"limit": 1000}
            )
            for f in folder_files:
                if f["name"].endswith(".html"):
                    hash_ = f["name"].replace(".html", "")
                    all_files.append({"path": f"{folder}/{f['name']}", "hash": hash_})

    if not all_files:
        return []

    # Find which hashes already exist in listings
    hashes = [f["hash"] for f in all_files]
    result = db.table("listings").select("url_hash").in_("url_hash", hashes).execute()
    done = {row["url_hash"] for row in result.data}

    return [f for f in all_files if f["hash"] not in done]


def download_html(path: str) -> str | None:
    db = get_client()
    try:
        data = db.storage.from_("raw-listings").download(path)
        return data.decode("utf-8")
    except Exception as e:
        print(f"    Download failed: {e}")
        return None


def get_url_for_hash(hash_: str) -> str | None:
    db = get_client()
    result = db.table("seen_urls").select("url").eq("url_hash", hash_).limit(1).execute()
    if result.data:
        return result.data[0]["url"]
    return None


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
    print("=== JobMatch extractor — Step 3 ===")

    print("\n[1/3] Finding unextracted files in Storage...")
    pending = get_unextracted_files()
    print(f"  Pending: {len(pending)}")

    if not pending:
        print("  Nothing to extract. Exiting.")
        return

    ok = 0
    low_conf = 0
    failed = 0

    print(f"\n[2/3] Extracting {len(pending)} listings with Claude...")
    for i, file in enumerate(pending, 1):
        hash_ = file["hash"]
        path = file["path"]
        print(f"  [{i}/{len(pending)}] {path}")

        html = download_html(path)
        if html is None:
            failed += 1
            continue

        try:
            fields = extract_listing(html)
        except Exception as e:
            print(f"    Extraction error: {e}")
            failed += 1
            continue

        if fields is None:
            print(f"    No tool call returned")
            failed += 1
            continue

        url = get_url_for_hash(hash_) or f"unknown:{hash_}"
        conf = fields.get("confidence", 0)
        status = "ok" if conf >= 0.6 else "low_confidence"
        print(f"    {fields.get('title', '?')} @ {fields.get('company', '?')} — conf={conf:.2f} [{status}]")

        try:
            write_listing(hash_, url, fields)
            if status == "ok":
                ok += 1
            else:
                low_conf += 1
        except Exception as e:
            print(f"    DB write failed: {e}")
            failed += 1

        # Respectful rate limiting
        time.sleep(0.5)

    print(f"\n[3/3] Done.")
    print(f"  OK: {ok}  Low-confidence: {low_conf}  Failed: {failed}")
    print(f"  Total in listings table: {ok + low_conf}")


if __name__ == "__main__":
    run()
