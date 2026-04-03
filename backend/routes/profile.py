from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from db.supabase_client import get_client
from datetime import datetime, timezone

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileIn(BaseModel):
    specialty: str
    years_experience: int
    region: str
    accepted_contracts: list[str]
    preferred_schedule: str | None = None
    min_salary: int | None = None
    licensure_held: list[str] = []


@router.get("")
def get_profile(user: dict = Depends(get_current_user)):
    db = get_client()
    result = db.table("profiles").select("*").eq("user_id", user["user_id"]).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result.data[0]


@router.post("")
def upsert_profile(body: ProfileIn, user: dict = Depends(get_current_user)):
    db = get_client()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "user_id": user["user_id"],
        "updated_at": now,
        **body.model_dump(),
    }
    result = db.table("profiles").upsert(row, on_conflict="user_id").execute()
    return result.data[0] if result.data else row


@router.delete("")
def delete_account(user: dict = Depends(get_current_user)):
    db = get_client()
    user_id = user["user_id"]
    db.table("matches").delete().eq("user_id", user_id).execute()
    db.table("profiles").delete().eq("user_id", user_id).execute()
    db.auth.admin.delete_user(user_id)
    return {"deleted": True}
