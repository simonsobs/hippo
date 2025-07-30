"""
The main FastAPI endpoints.
"""

from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from pymongo import AsyncMongoClient
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from hipposerve.api.product import product_router
from hipposerve.api.relationships import relationship_router
from hipposerve.api.soauth import setup_auth
from hipposerve.database import BEANIE_MODELS
from hipposerve.service.collection import CollectionNotFound
from hipposerve.service.product import ProductNotFound
from hipposerve.settings import SETTINGS
from hipposerve.storage import Storage
from hipposerve.web.auth import UnauthorizedException
from hipposerve.web.router import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application services."""
    app.db = AsyncMongoClient(SETTINGS.mongo_uri).account
    await init_beanie(app.db, document_models=BEANIE_MODELS)
    app.storage = Storage(
        url=SETTINGS.minio_url,
        presign_url=SETTINGS.minio_presign_url,
        upgrade_presign_url_to_https=SETTINGS.minio_upgrade_presign_url_to_https,
        secure=SETTINGS.minio_secure,
        cert_check=SETTINGS.minio_cert_check,
        access_key=SETTINGS.minio_access,
        secret_key=SETTINGS.minio_secret,
    )

    logger.info("Startup complete")
    yield
    logger.info("Shutdown complete")


app = setup_auth(
    FastAPI(
        title=SETTINGS.title,
        description=SETTINGS.description,
        lifespan=lifespan,
        docs_url="/docs" if SETTINGS.debug else None,
        redoc_url="/redoc" if SETTINGS.debug else None,
    )
)

# Routers
app.include_router(product_router)
app.include_router(relationship_router)

if SETTINGS.web:  # pragma: no cover
    from hipposerve.web import static_files, web_router

    logger.info("Web interface enabled, serving it from {}", web_router.prefix)

    app.include_router(web_router)
    app.mount(**static_files)

    @app.exception_handler(UnauthorizedException)
    async def unauthorized_exception_handler(
        request: Request, exc: UnauthorizedException
    ):
        if request.user.is_authenticated:
            return HTMLResponse(
                content="You do not have permission to access this resource",
                status_code=403,
            )
        else:
            return RedirectResponse(app.login_url)

    def not_found_template(
        request: Request,
        type: str,
        requested_id: str | None,
    ):
        error_details = {
            "type": type,
        }

        if error_details["type"] != "generic":
            error_details["requested_id"] = requested_id

        return templates.TemplateResponse(
            "404.html",
            {
                "request": request,
                "error_details": error_details,
                "user": request.user.display_name,
                "web_root": SETTINGS.web_root,
            },
            status_code=404,
        )

    if not SETTINGS.debug:
        logger.warning(
            "Debug mode is disabled, enabling wide-ranging HTTPException handler"
        )

        @app.exception_handler(HTTPException)
        async def page_not_found_handler(
            request: Request,
            exc: HTTPException,
        ):
            return not_found_template(request, "generic", None)

        logger.warning(
            "Debug mode is disabled, enabling wide-ranging validation handler"
        )

        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(
            request: Request,
            exc: RequestValidationError,
        ):
            requested_item_type = "generic"
            requested_id = None
            try:
                requested_id = request.path_params["id"]
                if request.url.path.find("collections"):
                    requested_item_type = "collection"
                elif request.url.path.find("products"):
                    requested_item_type = "product"
                return not_found_template(request, requested_item_type, requested_id)
            except KeyError:
                return not_found_template(request, requested_item_type, requested_id)

    @app.exception_handler(CollectionNotFound)
    async def collection_not_found_handler(
        request: Request,
        exc: CollectionNotFound,
    ):
        requested_id = request.path_params["id"]
        return not_found_template(request, "collection", requested_id)

    @app.exception_handler(ProductNotFound)
    async def product_not_found_handler(
        request: Request,
        exc: ProductNotFound,
    ):
        requested_id = request.path_params["id"]
        return not_found_template(request, "product", requested_id)

    @app.get("/")
    async def web_redirect(request: Request):
        return RedirectResponse(SETTINGS.web_root)


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
