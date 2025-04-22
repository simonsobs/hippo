"""
Utilities for product search and rendering search results.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from hippometa import ALL_METADATA
from hipposerve.service import collection, product
from hipposerve.settings import SETTINGS

from .auth import PotentialLoggedInUser
from .router import templates

router = APIRouter()


# Query and render search results from the navigation bar's "search by name" option
@router.get("/search/results", response_class=HTMLResponse)
async def search_results_view(
    request: Request,
    user: PotentialLoggedInUser,
    q: str = None,
    filter: str = "products",
):
    if filter == "products":
        results = await product.search_by_name(q)
    elif filter == "collections":
        results = await collection.search_by_name(q)
    else:
        results = []

    return templates.TemplateResponse(
        "search_results.html",
        {
            "request": request,
            "query": q,
            "filter": filter,
            "results": results,
            "user": user,
            "web_root": SETTINGS.web_root,
        },
    )


# Query and render search results for the more complex metadata request
@router.get("/searchmetadata/results", response_class=HTMLResponse)
async def searchmetadata_results_view(
    request: Request,
    user: PotentialLoggedInUser,
    q: str = None,
    filter_on: str = "products",
):
    query_params = dict(request.query_params)

    # Determine which metadata_class we're searching on so we can get the fields;
    # we will use the fields with the query_params to craft type-specific queries
    metadata_class = next(
        v
        for v in ALL_METADATA.values()
        if v.schema()["title"] == query_params["metadata_type"]
    )
    metadata_fields = metadata_class.model_json_schema()["properties"]

    # Create a dict for the following pre-processing of metadata_fields
    simplified_metadata_fields = {}

    # Do some pre-processing of the metadata_fields to simplify query logic
    for field_key, field_data in metadata_fields.items():
        if field_key == "metadata_type" or "additionalProperties" in field_data:
            continue

        if "anyOf" in field_data:
            true_type = [x for x in field_data["anyOf"] if x["type"] != "null"][0]
            field_data = {**field_data, **true_type}
            field_data.pop("anyOf")

        simplified_metadata_fields[field_key] = field_data

    # Create a dict to hold the queries as we craft them below
    metadata_filters = {}

    for key, value in query_params.items():
        if key == "metadata_type":
            continue

        field = simplified_metadata_fields[key]
        field_type = field.get("type", None)

        # Query for enums; no query logic needed
        if "enum" in field:
            metadata_filters[key] = value
        # Query for comma-separated lists
        elif field_type == "array":
            metadata_filters[key] = {"$in": [v.strip() for v in value.split(",")]}
        # Query for number ranges
        elif field_type == "number" and "," in value:
            min, max = value.split(",")
            if min != "undefined":
                metadata_filters[key] = {"$gte": min}
            if max != "undefined":
                metadata_filters[key] = metadata_filters.get(key, {})
                metadata_filters[key]["$lte"] = max
        # Default query applies regex and case insensitivity
        else:
            metadata_filters[key] = {"$regex": value, "$options": "i"}

    results = await product.search_by_metadata(metadata_filters)

    return templates.TemplateResponse(
        "search_results.html",
        {
            "request": request,
            "query": q,
            "filter": filter_on,
            "results": results,
            "metadata_filters": metadata_filters,
            "metadata_type": query_params["metadata_type"],
            "user": user,
            "web_root": SETTINGS.web_root,
        },
    )


@router.get("/searchmetadata", response_class=HTMLResponse)
async def search_metadata_view(
    request: Request,
    user: PotentialLoggedInUser,
):
    metadata_info = {}

    for metadata_class in ALL_METADATA.values():
        if metadata_class is None:
            continue

        class_schema = metadata_class.model_json_schema()
        class_name = class_schema["title"]
        class_fields = class_schema["properties"]

        # Separate number fields from other types so we can render the number
        # fields together in the metadata search page
        number_fields = {}
        other_fields = {}

        for field_key, field_data in class_fields.items():
            # additionalProperties means the field is a dictionary with arbitrary keys
            # we can't search on that.
            if field_key == "metadata_type" or "additionalProperties" in field_data:
                continue

            if "anyOf" in field_data:
                # This occurs when we have x | None, extract x and stick it in the field_data
                true_type = [x for x in field_data["anyOf"] if x["type"] != "null"][0]
                field_data = {**field_data, **true_type}
                field_data.pop("anyOf")

            field_type = field_data.get("type", None)

            if "enum" in field_data:
                other_fields[field_key] = {
                    "type": "enum",
                    "title": field_data["title"],
                    "options": field_data["enum"],
                }
            elif field_type == "array":
                other_fields[field_key] = {
                    "type": "array",
                    "list_arg": field_data["items"]["type"],
                    "title": field_data["title"],
                }
            elif field_type == "number":
                number_fields[field_key] = {
                    "type": "number",
                    "title": field_data["title"],
                    "min": field_data.get("min", None),
                    "max": field_data.get("max", None),
                }
            else:
                other_fields[field_key] = {
                    "type": field_type,
                    "title": field_data["title"],
                }

        metadata_info[class_name] = {**number_fields, **other_fields}

    return templates.TemplateResponse(
        "search_metadata.html",
        {
            "request": request,
            "metadata": metadata_info,
            "user": user,
            "web_root": SETTINGS.web_root,
        },
    )
