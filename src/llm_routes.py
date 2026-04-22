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
    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.get_json() or {}
        user_message = (data.get("message") or "").strip()
        current_results = data.get("current_results", []) # <-- Reads from React!

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        api_key = os.getenv("SPARK_API_KEY")
        if not api_key:
            return jsonify({"error": "SPARK_API_KEY not set"}), 500

        client = LLMClient(api_key=api_key)

        if current_results:
            context_text = "\n\n---\n\n".join(
                (
                    f"Shoe: {shoe.get('shoe_name')}\n"
                    f"Category: {shoe.get('category')}\n"
                    f"Match score: {shoe.get('match_score')}\n"
                    f"Reasons: {', '.join(shoe.get('match_reasons', []))}\n"
                    f"Top terms: {', '.join(shoe.get('top_terms', []))}\n"
                    f"Specs: {shoe.get('specs', 'No specs available')}\n"
                    f"Sample reviews: {' | '.join(shoe.get('sample_reviews', []))}"
                )
                for shoe in current_results[:6] 
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a sneaker recommendation assistant helping a user who is looking at a specific list of sneakers. "
                        "Use ONLY the provided sneaker results to answer their questions. "
                        "Explain matches in terms of review evidence and explicitly say when physical measurements are unavailable. "
                        "IMPORTANT: Do not use Markdown formatting like asterisks (*) or bold text (**). Output clean, plain text and use simple dashes (-) for lists."
                    ),
                },
                {"role": "user", "content": f"Currently displayed sneakers:\n\n{context_text}\n\nUser question: {user_message}"},
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
