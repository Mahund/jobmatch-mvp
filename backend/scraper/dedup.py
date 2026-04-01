import hashlib
from datetime import datetime, timezone
from db.supabase_client import get_client


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def filter_new_urls(urls: list[str]) -> list[str]:
    """Return only URLs not already in seen_urls."""
    if not urls:
        return []

    hashes = [url_hash(u) for u in urls]
    db = get_client()

    result = db.table("seen_urls").select("url_hash").in_("url_hash", hashes).execute()
    seen = {row["url_hash"] for row in result.data}

    return [u for u, h in zip(urls, hashes) if h not in seen]


def mark_seen(urls: list[str]) -> None:
    """Insert URLs into seen_urls to prevent reprocessing."""
    if not urls:
        return

    db = get_client()
    rows = [
        {
            "url_hash": url_hash(u),
            "url": u,
            "first_seen": datetime.now(timezone.utc).isoformat(),
        }
        for u in urls
    ]
    db.table("seen_urls").upsert(rows, on_conflict="url_hash").execute()
