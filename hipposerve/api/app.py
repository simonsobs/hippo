"""
The main FastAPI endpoints.
"""

from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from hipposerve.api.product import product_router
from hipposerve.api.relationships import relationship_router
from hipposerve.api.users import users_router
from hipposerve.database import BEANIE_MODELS
from hipposerve.service.users import UserNotFound
from hipposerve.settings import SETTINGS
from hipposerve.storage import Storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application services."""
    app.db = AsyncIOMotorClient(SETTINGS.mongo_uri).account
    await init_beanie(app.db, document_models=BEANIE_MODELS)
    app.storage = Storage(
        url=SETTINGS.minio_url,
        access_key=SETTINGS.minio_access,
        secret_key=SETTINGS.minio_secret,
    )

    if SETTINGS.create_test_user:
        from hipposerve.service import users

        try:
            user = await users.read(name="admin")
        except UserNotFound:
            user = await users.create(
                name="admin",
                password=SETTINGS.test_user_password,
                privileges=list(users.Privilege),
                hasher=SETTINGS.hasher,
            )

        await user.set({users.User.api_key: SETTINGS.test_user_api_key})
        logger.warning(
            f"Created test user: {user.name} with API key: {user.api_key}, "
            "you should NOT see this message in production"
        )

    logger.info("Startup complete")
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title=SETTINGS.title,
    description=SETTINGS.description,
    lifespan=lifespan,
    docs_url="/docs" if SETTINGS.debug else None,
    redoc_url="/redoc" if SETTINGS.debug else None,
)

# Routers
app.include_router(users_router)
app.include_router(product_router)
app.include_router(relationship_router)

if SETTINGS.web:  # pragma: no cover
    from hipposerve.web import static_files, web_router

    logger.info(f"Web interface enabled, serving it from {web_router.prefix}")

    app.include_router(web_router)
    app.mount(**static_files)

if SETTINGS.add_cors:
    logger.warning(
        "Completely open CORS policy enabled, designed for testing and development"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
