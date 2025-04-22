"""
Web frontend for hippo. This consumes the service layer.

NOTE: Code coverage is an explicit NON-goal for the web
      frontend, and as such it is excluded from our
      coverage metrics.
"""

from hashlib import md5
from typing import Literal

from beanie import PydanticObjectId
from fastapi import Request

from hipposerve.database import Collection
from hipposerve.service import collection, product
from hipposerve.settings import SETTINGS

from .auth import PotentialLoggedInUser
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
async def index(request: Request, user: PotentialLoggedInUser):
    products = await product.read_most_recent(fetch_links=True, maximum=16)
    collections = await collection.read_most_recent(fetch_links=True, maximum=16)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "products": products,
            "collections": collections,
            "user": user,
            "web_root": SETTINGS.web_root,
        },
    )


@web_router.get("/products/{id}")
async def product_view(request: Request, id: str, user: PotentialLoggedInUser):
    product_instance = await product.read_by_id(id)
    sources = await product.read_files(product_instance, storage=request.app.storage)
    # Grab the history!
    latest_version = await product.walk_to_current(product_instance)
    version_history = await product.walk_history(latest_version)

    return templates.TemplateResponse(
        "product.html",
        {
            "request": request,
            "product": product_instance,
            "sources": sources,
            "versions": version_history,
            "user": user,
            "web_root": SETTINGS.web_root,
        },
    )


@web_router.get("/collections/{id}")
async def collection_view(
    request: Request, id: PydanticObjectId, user: PotentialLoggedInUser
):
    collection_instance = await collection.read(id)
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
    return templates.TemplateResponse(
        "collection.html",
        {
            "request": request,
            "collection": collection_instance,
            "parents_overflow_content": parents_overflow_content,
            "children_overflow_content": children_overflow_content,
            "cmap": cmap,
            "user": user,
            "web_root": SETTINGS.web_root,
        },
    )
