"""
LLM RAG routes for SneakPeek.
Only loaded when USE_LLM = True in routes.py.

Pipeline
--------
1. POST /api/sneakers hits IR after the LLM first expands the user query
   (expand_query is called from routes.py before search_shoes).
2. GET  /api/rag-summary  — streams a synthesized answer given original query +
   IR-expanded query + top IR results (the full RAG loop visible to the user).
3. POST /api/explain      — per-shoe streaming explanation (polish).
"""
import json
import os
import logging
from flask import request, jsonify, Response, stream_with_context
from infosci_spark_client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Query expansion — LLM transforms user prose → IR keyword string
# ---------------------------------------------------------------------------

_EXPAND_SYSTEM_PROMPT = (
    "You are a sneaker search query optimizer for a TF-IDF retrieval system. "
    "Transform the user's natural language description into a concise list of "
    "technical sneaker-related keywords that will maximize retrieval recall. "
    "Return ONLY a space-separated list of lowercase keywords. "
    "No explanation, no punctuation beyond spaces, no full sentences."
)


def expand_query(user_query: str, category: str, api_key: str) -> str:
    """Call the LLM to rewrite user_query into IR-friendly keywords.

    Falls back to the original query on any error so IR always runs.
    """
    client = LLMClient(api_key=api_key)
    messages = [
        {"role": "system", "content": _EXPAND_SYSTEM_PROMPT},
        {"role": "user", "content": f"Category: {category}\nQuery: {user_query}"},
    ]
    result = ""
    try:
        for chunk in client.chat(messages, stream=True):
            if chunk.get("content"):
                result += chunk["content"]
    except Exception as exc:
        logger.error("Query expansion error: %s", exc)
        return user_query
    expanded = result.strip()
    return expanded if expanded else user_query


# ---------------------------------------------------------------------------
# 2. RAG summary — synthesises top IR results into a user-facing answer
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM_PROMPT = (
    "You are a sneaker analyst for SneakPeek. "
    "The user described what they want in natural language. "
    "An LLM expanded that description into IR keywords, and the IR system "
    "retrieved the top matching shoes using those keywords. "
    "Write 3-4 sentences that directly answer the user's original query: "
    "compare the retrieved shoes, explain why the best ones fit using the review evidence "
    "and matched terms provided, and note any trade-offs. "
    "Be specific and concrete. No markdown, no numbered ranking, plain flowing prose. "
    "Use only shoe names from the retrieved results."
)


def _build_summary_context(query: str, ir_query: str, results: list) -> str:
    lines = [
        f"User's original query: {query}",
        f"LLM-expanded IR query: {ir_query}",
        "",
        "Top IR-retrieved shoes:",
    ]
    for i, shoe in enumerate(results[:4], 1):
        lines.append(
            f"{i}. {shoe.get('shoe_name')} ({shoe.get('category')}) "
            f"— IR match score: {shoe.get('match_score')}%"
        )
        if shoe.get("review_evidence"):
            lines.append(f"   Review evidence: {shoe.get('review_evidence')}")
        top = shoe.get("top_terms") or []
        if top:
            lines.append(f"   Top matched terms: {', '.join(top[:6])}")
    return "\n".join(lines)


def register_rag_summary_route(app):
    """Register POST /api/rag-summary — streaming synthesis of top IR results."""

    @app.route("/api/rag-summary", methods=["POST"])
    def rag_summary():
        data = request.get_json() or {}
        query = (data.get("query") or "").strip()
        ir_query = (data.get("ir_query") or query).strip()
        results = data.get("results") or []

        if not query or not results:
            return jsonify({"error": "query and results are required"}), 400

        api_key = os.getenv("SPARK_API_KEY")
        if not api_key:
            return jsonify({"error": "SPARK_API_KEY not set"}), 500

        client = LLMClient(api_key=api_key)
        context = _build_summary_context(query, ir_query, results)
        messages = [
            {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        def generate():
            try:
                for chunk in client.chat(messages, stream=True):
                    if chunk.get("content"):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as exc:
                logger.error("RAG summary streaming error: %s", exc)
                yield f"data: {json.dumps({'error': 'Streaming error occurred'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


# ---------------------------------------------------------------------------
# 3. Per-shoe explain (polish) — kept from earlier iteration
# ---------------------------------------------------------------------------

_EXPLAIN_SYSTEM_PROMPT = (
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
    """Register POST /api/explain — streaming per-shoe RAG explanation."""

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
            {"role": "system", "content": _EXPLAIN_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        def generate():
            try:
                for chunk in client.chat(messages, stream=True):
                    if chunk.get("content"):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as exc:
                logger.error("Explain streaming error: %s", exc)
                yield f"data: {json.dumps({'error': 'Streaming error occurred'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
