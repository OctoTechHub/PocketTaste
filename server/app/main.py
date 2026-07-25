"""Application factory. Wiring only — no business logic lives here."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.container import build_container
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.data.mongo import MongoGateway

DESCRIPTION = """
An explainable creator-intelligence and discovery layer for long-form audio stories.

It captures listener behaviour, derives demand signals, screens uploads for
duplication, and produces recommendations with a full score breakdown. It is an
independent layer — it does not replace or depend on any platform-side recommender.

**Start here**
1. `POST /pipeline/run` — build embeddings, features and the demand report
2. `POST /recommendations` — personalised results with per-signal contributions
3. `POST /similarity/check` — screen a draft before upload
4. `GET  /insights/opportunities` — under-served genre/language cells
5. `POST /evaluation/run` — Recall@K / NDCG@K against popularity and random baselines

Every aggregate response carries a `provenance` field. `synthetic_simulation` means
the numbers came from the built-in simulator and are not real audience data.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging()
    logger = get_logger(__name__)

    gateway = MongoGateway(settings)
    connected = await gateway.connect()
    container = build_container(settings, gateway)
    app.state.container = container

    if connected:
        await container.warm_up()
        await container.scheduler.start()
    else:
        logger.warning("Running without storage — endpoints that need MongoDB will return 503.")

    logger.info(
        "%s v%s ready | embeddings=%s | llm=%s | mongo=%s",
        settings.app_name,
        settings.app_version,
        container.embeddings.backend,
        container.llm.describe()["openai"] or "unavailable",
        connected,
    )
    try:
        yield
    finally:
        await container.scheduler.stop()
        await gateway.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
