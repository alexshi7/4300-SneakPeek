"""
LLM RAG explain route for SneakPeek.
Only loaded when USE_LLM = True in routes.py.

POST /api/explain
  Body: { query: str, shoe: { shoe_name, category, match_score, top_terms,
                               review_evidence, sample_reviews, specs, match_reasons } }
  Response: SSE stream of { content: str } chunks.

The LLM receives the user's original query and the IR-retrieved shoe's review
data, then explains why the IR system selected this shoe for that query.
"""
import json
import os
import logging
from flask import request, jsonify, Response, stream_with_context
from infosci_spark_client import LLMClient

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a sneaker analyst for SneakPeek, a review-backed shoe search engine. "
    "A user submitted a search query and the IR system retrieved a specific shoe. "
    "Your job is to explain in 3-4 concise sentences — using only the provided review "
    "evidence, top matched terms, and specs — why this shoe is a strong match for the "
    "user's query. Be specific: reference actual review phrases or specs. "
    "Do not recommend other shoes. Do not use Markdown bold or bullet points. "
    "Write in plain flowing prose."
)


def _build_shoe_context(query: str, shoe: dict) -> str:
    specs = shoe.get("specs") or {}
    spec_lines = [
        f"  {k.replace('_', ' ')}: {v}"
        for k, v in specs.items()
        if v is not None and v != ""
    ]
    reviews = shoe.get("sample_reviews") or []

    lines = [
        f"User query: {query}",
        "",
        f"Shoe retrieved by IR: {shoe.get('shoe_name')} ({shoe.get('category')})",
        f"IR match score: {shoe.get('match_score')}%",
        f"Top matched review terms: {', '.join(shoe.get('top_terms', []))}",
        f"IR match reasons: {', '.join(shoe.get('match_reasons', []))}",
        f"Review evidence highlight: {shoe.get('review_evidence', '')}",
    ]
    if spec_lines:
        lines.append("Specs:")
        lines.extend(spec_lines)
    if reviews:
        lines.append("Sample reviewer quotes:")
        for rev in reviews[:3]:
            lines.append(f'  "{rev}"')

    return "\n".join(lines)


def register_explain_route(app):
    """Register POST /api/explain — streaming RAG explanation for a single IR result."""

    @app.route("/api/explain", methods=["POST"])
    def explain():
        data = request.get_json() or {}
        query = (data.get("query") or "").strip()
        shoe = data.get("shoe") or {}

        if not query or not shoe.get("shoe_name"):
            return jsonify({"error": "query and shoe are required"}), 400

        api_key = os.getenv("SPARK_API_KEY")
        if not api_key:
            return jsonify({"error": "SPARK_API_KEY not set"}), 500

        client = LLMClient(api_key=api_key)
        context = _build_shoe_context(query, shoe)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        def generate():
            try:
                for chunk in client.chat(messages, stream=True):
                    if chunk.get("content"):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as e:
                logger.error(f"Explain streaming error: {e}")
                yield f"data: {json.dumps({'error': 'Streaming error occurred'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
