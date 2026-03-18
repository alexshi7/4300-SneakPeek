"""
Routes for serving the React app and shoe retrieval API.

The current retrieval layer uses Foot Locker review text and can optionally
merge physical measurements from src/shoe_specs.csv if you add that file later.
"""
import os
from flask import jsonify, request, send_from_directory

from shoe_search import load_catalog, search_shoes

USE_LLM = False


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
        return jsonify(payload)

    if USE_LLM:
        from llm_routes import register_chat_route

        register_chat_route(app, search_shoes)
