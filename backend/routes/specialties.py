from fastapi import APIRouter, Response
from db.supabase_client import get_client

router = APIRouter(prefix="/specialties", tags=["specialties"])


@router.get("")
def get_specialties(response: Response) -> list[str]:
    response.headers["Cache-Control"] = "public, max-age=300"

    db = get_client()

    # Try RPC first (if it exists in the environment)
    try:
        result = db.rpc("list_distinct_specialties").execute()
        data = result.data or []
        if data:
            if isinstance(data[0], dict):
                return sorted(set(row["specialty"] for row in data if row.get("specialty")))
            return sorted(set(s for s in data if s))
    except Exception:
        # Fall back to direct query if RPC doesn't exist
        pass

    # Direct query: distinct specialties from listings, sorted
    try:
        result = db.table("listings").select("specialty").execute()
        data = result.data or []
        specialties = sorted(set(row["specialty"] for row in data if row.get("specialty")))
        return specialties
    except Exception as e:
        # Return empty list if query fails; caller should handle gracefully
        return []
