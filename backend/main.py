import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import matches, profile, rematch, specialties

app = FastAPI(title="JobMatch API")

_raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
_origins = [o.strip() for o in _raw.split(",") if o.strip()] or ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router)
app.include_router(profile.router)
app.include_router(rematch.router)
app.include_router(specialties.router)


@app.get("/health")
def health():
    return {"status": "ok"}
