from fastapi import APIRouter
from db.supabase_client import get_client

router = APIRouter(prefix="/specialties", tags=["specialties"])


@router.get("")
def get_specialties() -> list[str]:
    db = get_client()
    result = (
        db.table("listings")
        .select("specialty")
        .not_.is_("specialty", "null")
        .execute()
    )
    seen: set[str] = set()
    unique: list[str] = []
    for row in result.data:
        s = row.get("specialty", "")
        if s and s not in seen:
            seen.add(s)
            unique.append(s)
    return sorted(unique)
