import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import matches, profile, rematch

app = FastAPI(title="JobMatch API")

_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

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


@app.get("/health")
def health():
    return {"status": "ok"}
