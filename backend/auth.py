"""
JWT auth dependency for FastAPI.
Validates Supabase JWTs by calling Supabase's get_user() endpoint.
Supports both HS256 and ES256 key formats.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from db.supabase_client import get_client

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    token = credentials.credentials
    try:
        db = get_client()
        response = db.auth.get_user(token)
        user_id = response.user.id if response.user else None
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"user_id": user_id}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
