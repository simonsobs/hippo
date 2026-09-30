"""
Social previews for the web frontend.

Link unfurlers (Slack, Discord, etc.) are not logged in, so without this
they get redirected to the login page and render an empty preview. The
middleware here intercepts bot requests to the web frontend and returns a
minimal page containing only OpenGraph metadata. No product or collection
information is included, as the bot (or anyone spoofing its user agent)
is not authenticated.
"""

from html import escape
from urllib.parse import urljoin

from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from user_agents import parse

from hipposerve.settings import SETTINGS

from .router import web_router

PREVIEW_IMAGE = "apple-touch-icon.png"


def is_bot(request: Request) -> bool:
    ua_string = request.headers.get("user-agent", "")
    return parse(ua_string).is_bot


def social_preview_response(request: Request) -> HTMLResponse:
    # Unfurlers require absolute URLs; web_root may be relative or absolute.
    page_url = str(request.url)
    image_url = urljoin(page_url, f"{SETTINGS.web_root}/static/{PREVIEW_IMAGE}")

    title = escape(SETTINGS.title)
    description = escape(SETTINGS.description)
    image_url = escape(image_url)
    page_url = escape(page_url)

    return HTMLResponse(
        content=f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="{title}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{image_url}">
    <meta property="og:image:width" content="1024">
    <meta property="og:image:height" content="1024">
    <meta property="og:image:alt" content="Simons Observatory logo">
    <meta property="og:url" content="{page_url}">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="{image_url}">
  </head>
  <body>
    Social preview only.
  </body>
</html>
""",
        status_code=200,
    )


class SocialPreviewMiddleware(BaseHTTPMiddleware):
    """
    Serve OpenGraph metadata to bots requesting web frontend pages, instead
    of redirecting them to log in. Static files are passed through so that
    the preview image itself can be fetched.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        prefix = web_router.prefix
        in_web = path == prefix or path.startswith(f"{prefix}/")
        is_static = path.startswith(f"{prefix}/static/")

        if (
            request.method in ("GET", "HEAD")
            and in_web
            and not is_static
            and is_bot(request)
        ):
            return social_preview_response(request)

        return await call_next(request)
