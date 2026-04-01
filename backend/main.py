from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import matches, profile, rematch

app = FastAPI(title="JobMatch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened after Vercel deploy URL is known
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
