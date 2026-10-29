from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.config import settings
from app.core.job_store import job_store
from app.routers import jobs, molecules, sample, screening
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VirtualScreener API starting up")
    job_store.init_persistence(
        settings.db_path,
        max_jobs=settings.max_jobs,
        ttl_hours=settings.job_ttl_hours,
    )
    # Warm up ML scorer at startup
    from app.services.ml_scoring import get_scorer

    get_scorer(
        chemprop_checkpoint=settings.chemprop_checkpoint,
        deepchem_model_dir=settings.deepchem_model_dir,
    )
    yield
    logger.info("VirtualScreener API shutting down")


app = FastAPI(
    title="VirtualScreener API",
    description=(
        "AI-powered virtual screening platform: "
        "3-tier pipeline (RDKit Tier1 → Chemprop+DeepChem Tier2 → AutoDock Vina Tier3)"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Per-IP sliding-window rate limit on compute endpoints.
_RATE_LIMITED_PATHS = {
    f"{settings.api_prefix}/screen",
    f"{settings.api_prefix}/sample/screen",
}
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_compute(request, call_next):
    if request.method == "POST" and request.url.path in _RATE_LIMITED_PATHS:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = _hits[ip]
        while hits and now - hits[0] > settings.rate_limit_window_seconds:
            hits.popleft()
        if len(hits) >= settings.rate_limit_jobs:
            retry = int(settings.rate_limit_window_seconds - (now - hits[0])) + 1
            return JSONResponse(
                {
                    "detail": (
                        f"Rate limit: max {settings.rate_limit_jobs} screening "
                        f"jobs per {settings.rate_limit_window_seconds}s"
                    )
                },
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)
    return await call_next(request)

app.include_router(screening.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(molecules.router, prefix=settings.api_prefix)
app.include_router(sample.router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


# ── Hugging Face Spaces: serve built React app as static files ────────────────
_static_dir = Path("/app/static")
if os.getenv("HF_STATIC"):
    if _static_dir.exists():
        app.mount(
            "/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets"
        )

        @app.get("/", include_in_schema=False)
        async def spa_root():
            return FileResponse(str(_static_dir / "index.html"))

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            candidate = _static_dir / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(_static_dir / "index.html"))

    else:
        logger.warning("HF_STATIC set but static dir not found at %s", _static_dir)
