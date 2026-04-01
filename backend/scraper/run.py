"""
Step 2 orchestrator: scrape → dedup → upload raw HTML to Supabase Storage.
Run with:  python -m scraper.run
"""
import sys
import time
import random
from datetime import date
from pathlib import Path

# Allow running from backend/ dir
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.fetch import get_listing_urls, fetch_listing_html
from scraper.dedup import url_hash, filter_new_urls, mark_seen
from db.supabase_client import get_client


def upload_html(html: str, hash_: str) -> str:
    """Upload raw HTML to storage bucket. Returns the storage path."""
    db = get_client()
    today = date.today().isoformat()
    path = f"{today}/{hash_}.html"

    db.storage.from_("raw-listings").upload(
        path=path,
        file=html.encode("utf-8"),
        file_options={"content-type": "text/html; charset=utf-8", "upsert": "true"},
    )
    return path


def run():
    print("=== JobMatch scraper — Step 2 ===")

    print("\n[1/3] Collecting listing URLs from Computrabajo...")
    all_urls = get_listing_urls()
    print(f"  Total found: {len(all_urls)}")

    print("\n[2/3] Deduplicating against seen_urls...")
    new_urls = filter_new_urls(all_urls)
    print(f"  New (unseen): {len(new_urls)}")

    if not new_urls:
        print("  Nothing new today. Exiting.")
        return

    print(f"\n[3/3] Fetching and uploading {len(new_urls)} listings...")
    uploaded = []
    failed = []

    for i, url in enumerate(new_urls, 1):
        hash_ = url_hash(url)
        print(f"  [{i}/{len(new_urls)}] {url}")

        html = fetch_listing_html(url)
        if html is None:
            print(f"    FAILED to fetch")
            failed.append(url)
            continue

        try:
            path = upload_html(html, hash_)
            print(f"    Uploaded → {path}")
            uploaded.append(url)
        except Exception as e:
            print(f"    Storage upload failed: {e}")
            failed.append(url)
            continue

        time.sleep(random.uniform(1.0, 2.5))

    # Mark all successfully uploaded URLs as seen
    mark_seen(uploaded)

    print(f"\nDone. Uploaded: {len(uploaded)}  Failed: {len(failed)}")
    if failed:
        print("Failed URLs:")
        for u in failed:
            print(f"  {u}")


if __name__ == "__main__":
    run()
