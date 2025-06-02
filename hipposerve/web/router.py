"""
Builds the router and templates.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, PackageLoader

from hipposerve.settings import SETTINGS

web_router = APIRouter(prefix="/web")

potential_routes = ["hipposerve/web", "hippo/hipposerve/web", Path(__file__).parent]


def useful_variables(_):
    return {
        "soauth_enabled": SETTINGS.auth_system == "soauth",
        "soauth_login_url": f"{SETTINGS.soauth_service_url}/login/{SETTINGS.soauth_app_id}",
    }


for route in potential_routes:
    try:
        templates = Jinja2Templates(
            env=Environment(
                loader=PackageLoader("hipposerve", package_path="web/templates"),
                extensions=["jinja_markdown.MarkdownExtension"],
            ),
            context_processors=[useful_variables],
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
