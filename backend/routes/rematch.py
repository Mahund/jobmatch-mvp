from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from matching.engine import rematch as run_rematch

router = APIRouter(prefix="/rematch", tags=["rematch"])


@router.post("")
def trigger_rematch(user: dict = Depends(get_current_user)):
    try:
        matches = run_rematch(user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"matched": len(matches)}
