from fastapi import APIRouter, Response
from db.supabase_client import get_client

router = APIRouter(prefix="/specialties", tags=["specialties"])


@router.get("")
def get_specialties(response: Response) -> list[str]:
    response.headers["Cache-Control"] = "public, max-age=300"

    db = get_client()
    result = db.rpc("list_distinct_specialties").execute()

    data = result.data or []
    if not data:
        return []

    if isinstance(data[0], dict):
        return [row["specialty"] for row in data if row.get("specialty")]

    return [s for s in data if s]
