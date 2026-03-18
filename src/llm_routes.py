"""
LLM chat route for SneakPeek.
Only loaded when USE_LLM = True in routes.py.
"""
import json
import os
import re
import logging
from flask import request, jsonify, Response, stream_with_context
from infosci_spark_client import LLMClient

logger = logging.getLogger(__name__)


def llm_search_decision(client, user_message):
    messages = [
        {
            "role": "system",
            "content": (
                "You have access to a sneaker retrieval system backed by shoe reviews and optional specs. "
                "Reply with exactly: YES if the user wants shoe recommendations or shoe matching. "
                "Reply with exactly: NO for general conversation."
            ),
        },
        {"role": "user", "content": user_message},
    ]
    response = client.chat(messages)
    content = (response.get("content") or "").strip().upper()
    logger.info(f"LLM search decision: {content}")
    return bool(re.search(r"\bYES\b", content)) and not bool(re.search(r"\bNO\b", content)), None


def register_chat_route(app, shoe_search):
    """Register the /api/chat SSE endpoint. Called from routes.py."""

    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.get_json() or {}
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        api_key = os.getenv("API_KEY")
        if not api_key:
            return jsonify({"error": "API_KEY not set — add it to your .env file"}), 500

        client = LLMClient(api_key=api_key)
        use_search, _ = llm_search_decision(client, user_message)

        if use_search:
            search_payload = shoe_search(query=user_message, use_case=user_message, limit=6)
            sneakers = search_payload["results"]
            context_text = "\n\n---\n\n".join(
                (
                    f"Shoe: {shoe['shoe_name']}\n"
                    f"Category: {shoe['category']}\n"
                    f"Match score: {shoe['match_score']}\n"
                    f"Reasons: {', '.join(shoe['match_reasons'])}\n"
                    f"Top terms: {', '.join(shoe['top_terms'])}\n"
                    f"Sample reviews: {' | '.join(shoe['sample_reviews'])}"
                )
                for shoe in sneakers
            ) or "No matching sneakers found."
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a sneaker recommendation assistant. Use only the provided sneaker results. "
                        "Explain matches in terms of review evidence and explicitly say when physical measurements are unavailable."
                    ),
                },
                {"role": "user", "content": f"Sneaker information:\n\n{context_text}\n\nUser question: {user_message}"},
            ]
        else:
            messages = [
                {"role": "system", "content": "You are a helpful assistant for SneakPeek, a sneaker search app."},
                {"role": "user", "content": user_message},
            ]

        def generate():
            try:
                for chunk in client.chat(messages, stream=True):
                    if chunk.get("content"):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': 'Streaming error occurred'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
