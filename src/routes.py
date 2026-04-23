"""
Routes for serving the React app and shoe retrieval API.

The current retrieval layer uses Foot Locker review text and can optionally
merge physical measurements from src/shoe_specs.csv if you add that file later.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flask import jsonify, request, send_from_directory

from shoe_search import load_catalog, search_shoes

USE_LLM = True
IMAGE_CACHE = {}
IMAGE_TAG_PATTERNS = (
    re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE),
)


def _resolve_image_url(product_url):
    if not product_url:
        return ""

    cached = IMAGE_CACHE.get(product_url)
    if cached is not None:
        return cached

    parsed = urlparse(product_url)
    if parsed.scheme not in {"http", "https"}:
        IMAGE_CACHE[product_url] = ""
        return ""

    request_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        page_request = Request(product_url, headers=request_headers)
        with urlopen(page_request, timeout=3) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(content_type, errors="ignore")
    except (TimeoutError, URLError, ValueError):
        IMAGE_CACHE[product_url] = ""
        return ""

    image_url = ""
    for pattern in IMAGE_TAG_PATTERNS:
        match = pattern.search(html)
        if match:
            image_url = match.group(1)
            break

    if image_url.startswith("//"):
        image_url = f"https:{image_url}"

    IMAGE_CACHE[product_url] = image_url
    return image_url


def register_routes(app):
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/api/config")
    def config():
        return jsonify(
            {
                "use_llm": USE_LLM,
                "catalog_size": len(load_catalog()),
            }
        )

    @app.route("/api/sneakers")
    def sneakers_search():
        query = request.args.get("query", "")
        category = request.args.get("category", "")
        use_case = request.args.get("use_case", "")
        limit = min(int(request.args.get("limit", 12)), 24)
        payload = search_shoes(query=query, category=category, use_case=use_case, limit=limit)

        urls = [item.get("footlocker_url", "") for item in payload.get("results", [])]
        if urls:
            with ThreadPoolExecutor(max_workers=4) as executor:
                resolved = list(executor.map(_resolve_image_url, urls))

            for item, image_url in zip(payload["results"], resolved):
                item["image_url"] = image_url

        return jsonify(payload)

    if USE_LLM:
        from llm_routes import register_explain_route

        register_explain_route(app)
