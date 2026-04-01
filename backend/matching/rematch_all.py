"""
Re-runs matching for every user that has a profile.
Called by GitHub Actions after each scrape+extract cycle.
Run with:  python -m matching.rematch_all
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from db.supabase_client import get_client
from matching.engine import rematch


def run():
    db = get_client()
    profiles = db.table("profiles").select("user_id").execute().data
    print(f"Rematching {len(profiles)} user(s)...")

    for row in profiles:
        user_id = row["user_id"]
        try:
            matches = rematch(user_id)
            print(f"  {user_id}: {len(matches)} matches")
        except Exception as e:
            print(f"  {user_id}: ERROR — {e}")

    print("Done.")


if __name__ == "__main__":
    run()
