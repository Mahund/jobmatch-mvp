from fastapi import APIRouter, Depends
from auth import get_current_user
from db.supabase_client import get_client

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("")
def get_matches(user: dict = Depends(get_current_user)):
    db = get_client()
    result = (
        db.table("matches")
        .select(
            "score, specialty_tier, is_new, matched_at,"
            "listings(url_hash, url, title, company, city, region, contract_type,"
            "schedule, salary_raw, specialty, years_experience, summary, modality)"
        )
        .eq("user_id", user["user_id"])
        .eq("filter_passed", True)
        .order("score", desc=True)
        .execute()
    )
    return result.data
