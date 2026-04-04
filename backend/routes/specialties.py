import logging
from fastapi import APIRouter, Response, HTTPException
from db.supabase_client import get_client

logger = logging.getLogger(__name__)
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
    except Exception as e:
        # Log the RPC failure for observability; fall back to direct query
        logger.info(f"RPC list_distinct_specialties unavailable, falling back to direct query: {e}")

    # Direct query: distinct specialties from listings, sorted
    try:
        result = db.table("listings").select("specialty").execute()
        data = result.data or []
        specialties = sorted(set(row["specialty"] for row in data if row.get("specialty")))
        return specialties
    except Exception as e:
        # Log and return 500 so callers can distinguish real errors from empty results
        logger.error(f"Failed to fetch specialties: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch specialties")
