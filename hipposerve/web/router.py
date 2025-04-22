"""
Builds the router and templates.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

web_router = APIRouter(prefix="/web")

potential_routes = ["hipposerve/web", "hippo/hipposerve/web", Path(__file__).parent]

for route in potential_routes:
    try:
        templates = Jinja2Templates(
            directory=f"{route}/templates",
            extensions=["jinja_markdown.MarkdownExtension"],
        )

        static_files = {
            "path": "/web/static",
            "name": "static",
            "app": StaticFiles(directory=f"{route}/static", follow_symlink=True),
        }

        break
    except (FileNotFoundError, RuntimeError):
        continue


if "templates" not in locals():
    raise FileNotFoundError("Could not find the templates directory.")

if "static_files" not in locals():
    raise FileNotFoundError("Could not find the static directory.")
