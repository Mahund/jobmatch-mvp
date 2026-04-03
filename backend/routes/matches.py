from fastapi import APIRouter, Depends, Query
from auth import get_current_user
from db.supabase_client import get_client

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("")
def get_matches(
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("score", pattern="^(score|published_date)$"),
):
    db = get_client()
    start = (page - 1) * page_size
    end = start + page_size - 1

    query = (
        db.table("matches")
        .select(
            "score, specialty_tier, is_new, matched_at,"
            "listings(url_hash, url, title, company, city, region, contract_type,"
            "schedule, salary_raw, specialty, years_experience, summary, modality, published_date)",
            count="exact",
        )
        .eq("user_id", user["user_id"])
        .eq("filter_passed", True)
    )

    if sort == "published_date":
        query = query.order("published_date", desc=True, foreign_table="listings")
    else:
        query = query.order("score", desc=True)

    result = query.range(start, end).execute()
    return {
        "matches": result.data,
        "total": result.count,
        "page": page,
        "page_size": page_size,
    }
