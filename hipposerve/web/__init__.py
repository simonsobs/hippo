"""
Web frontend for hippo. This consumes the service layer.

NOTE: Code coverage is an explicit NON-goal for the web
      frontend, and as such it is excluded from our
      coverage metrics.
"""

from hashlib import md5
from typing import Literal

from beanie import PydanticObjectId
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from loguru import logger

from hipposerve.database import Collection
from hipposerve.service import collection, product, storage
from hipposerve.settings import SETTINGS

from .auth import router as auth_router
from .router import static_files as static_files
from .router import templates, web_router
from .search import router as search_router

web_router.include_router(search_router)
web_router.include_router(auth_router)


def get_overflow_content(lst: list[Collection], type: Literal["collection", "product"]):
    if len(lst) < 6:
        return None

    overflow_content = ""
    for n in range(6, len(lst) + 1):
        overflow_content += f'<a href="{SETTINGS.web_root}/{type}s/{lst[n - 1].id}">{lst[n - 1].name}</a><br>'

    return overflow_content


def get_color_hash(id: str):
    return f"#{md5(id.encode('utf-8')).hexdigest()[:6]}"


def get_cmap(ids: list[str] = []):
    cmap = {}
    for id in ids:
        cmap[id] = get_color_hash(id)
    return cmap


@web_router.get("/")
async def index(request: Request):
    recent_products = await product.read_most_recent(
        groups=request.user.groups,
        scopes=request.auth.scopes,
        fetch_links=True,
        maximum=16,
    )
    recent_collections = await collection.read_most_recent(
        groups=request.user.groups, scopes=request.auth.scopes, maximum=16
    )
    pinned_products = await product.read_pinned(
        groups=request.user.groups,
        scopes=request.auth.scopes,
        fetch_links=True,
        maximum=16,
    )
    pinned_collections = await collection.read_pinned(
        groups=request.user.groups, scopes=request.auth.scopes, maximum=16
    )
    logger.info(
        "Index page requested by {} with {}/{} recent products/collections and {}/{} "
        "pinned products/collections, user has {} scopes",
        request.user.display_name,
        len(recent_products),
        len(recent_collections),
        len(pinned_products),
        len(pinned_collections),
        request.auth.scopes,
    )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "recent_products": recent_products,
            "recent_collections": recent_collections,
            "pinned_products": pinned_products,
            "pinned_collections": pinned_collections,
            "user": request.user.display_name,
            "web_root": SETTINGS.web_root,
        },
    )


@web_router.get("/products/{id}")
async def product_view(request: Request, id: str):
    product_instance = await product.read_by_id(
        id, request.user.groups, scopes=request.auth.scopes
    )
    # Grab the history!
    latest_version = await product.walk_to_current(
        product_instance, request.user.groups, scopes=request.auth.scopes
    )
    version_history = await product.walk_history(latest_version)

    logger.info(
        "Product page for {} requested by {}, user has {} scopes",
        id,
        request.user.display_name,
        request.auth.scopes,
    )

    return templates.TemplateResponse(
        "product.html",
        {
            "request": request,
            "product": product_instance,
            "sources": product_instance.sources,
            "versions": version_history,
            "user": request.user.display_name,
            "web_root": SETTINGS.web_root,
        },
    )


@web_router.get("/products/{id}/edit")
async def product_edit(request: Request, id: str):
    product_instance = await product.read_by_id(
        id, request.user.groups, scopes=request.auth.scopes
    )

    logger.info(
        "Product edit page for {} requested by {}, user has {} scopes",
        id,
        request.user.display_name,
        request.auth.scopes,
    )

    return templates.TemplateResponse(
        "product_edit.html",
        {
            "request": request,
            "product": product_instance,
            "user": request.user.display_name,
            "web_root": SETTINGS.web_root,
        },
    )


@web_router.get("/products/{id}/{slug}")
async def product_read_slug(request: Request, id: str, slug: str) -> RedirectResponse:
    product_instance = await product.read_by_id(
        id, request.user.groups, scopes=request.auth.scopes
    )

    # If they have not 401/403'd from reading the product, they can read sources
    try:
        presigned = await storage.read(
            file=product_instance.sources[slug], storage=request.app.storage
        )
    except (FileNotFoundError, KeyError):
        logger.warning(
            "Slug {} not found for product {}, requested by {}, user has {} scopes",
            slug,
            id,
            request.user.display_name,
            request.auth.scopes,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Slug {slug} not found for product {id}",
        )

    logger.info(
        "Product source {} for product {} requested by {}, user has {} scopes, redirecting",
        slug,
        id,
        request.user.display_name,
        request.auth.scopes,
    )

    return RedirectResponse(url=presigned, status_code=status.HTTP_302_FOUND)


@web_router.get("/collections/{id}/edit")
async def collection_edit(request: Request, id: PydanticObjectId):
    collection_instance = await collection.read(
        id, request.user.groups, scopes=request.auth.scopes
    )

    logger.info(
        "Collection edit page for {} requested by {}, user has {} scopes",
        id,
        request.user.display_name,
        request.auth.scopes,
    )

    return templates.TemplateResponse(
        "collection_edit.html",
        {
            "request": request,
            "collection": collection_instance,
            "user": request.user.display_name,
            "web_root": SETTINGS.web_root,
        },
    )


@web_router.get("/collections/{id}")
async def collection_view(request: Request, id: PydanticObjectId):
    collection_instance = await collection.read(
        id, request.user.groups, scopes=request.auth.scopes
    )
    parents_overflow_content = get_overflow_content(
        collection_instance.parent_collections, "collection"
    )
    children_overflow_content = get_overflow_content(
        collection_instance.child_collections, "collection"
    )
    cmap = get_cmap(
        [str(id)]
        + [str(x.id) for x in collection_instance.parent_collections]
        + [str(x.id) for x in collection_instance.child_collections]
    )
    logger.info(
        "Collection page for {} requested by {}, user has {} scopes",
        id,
        request.user.display_name,
        request.auth.scopes,
    )
    return templates.TemplateResponse(
        "collection.html",
        {
            "request": request,
            "collection": collection_instance,
            "parents_overflow_content": parents_overflow_content,
            "children_overflow_content": children_overflow_content,
            "cmap": cmap,
            "user": request.user.display_name,
            "web_root": SETTINGS.web_root,
            "api_root": SETTINGS.api_root,
        },
    )
