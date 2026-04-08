import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Spelix API", version="0.1.0")

# CORS per NFR-SECU-11: explicit origins only, no wildcard in production
_allowed_origins: list[str] = [
    "https://spelix.app",
]

# Development origins
if os.getenv("SPELIX_ENV", "production") == "development":
    _allowed_origins += [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

# Vercel preview deployments
_vercel_preview = os.getenv("VERCEL_PREVIEW_ORIGIN")
if _vercel_preview:
    _allowed_origins.append(_vercel_preview)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Upload-Offset",
        "Tus-Resumable",
        "Upload-Length",
    ],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
