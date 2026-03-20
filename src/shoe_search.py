import csv
import math
import os
import re
from collections import Counter


DATASETS = {
    "basketball": "basketball_data.csv",
    "running": "running_data.csv",
    "sneakers": "sneakers_data.csv",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "best",
    "but",
    "by",
    "for",
    "from",
    "good",
    "great",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "pair",
    "shoe",
    "shoes",
    "sneaker",
    "sneakers",
    "that",
    "the",
    "their",
    "them",
    "these",
    "this",
    "to",
    "very",
    "want",
    "with",
    "you",
    "your",
}

CATEGORY_HINTS = {
    "basketball": {
        "basketball",
        "court",
        "hoops",
        "hooper",
        "guard",
        "forward",
        "center",
        "traction",
        "lockdown",
    },
    "running": {
        "running",
        "run",
        "runner",
        "jog",
        "jogging",
        "marathon",
        "training",
        "walk",
        "walking",
    },
    "sneakers": {
        "casual",
        "everyday",
        "fashion",
        "lifestyle",
        "streetwear",
        "retro",
        "chunky",
    },
}

catalog_cache = None
idf_cache = None
indexed_catalog_cache = None


def _data_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalize_category(category):
    normalized = (category or "").strip().lower()
    if normalized == "lifestyle":
        return "sneakers"
    return normalized


def _tokenize(text):
    return [
        token
        for token in TOKEN_RE.findall((text or "").lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def _top_terms(text, limit=8):
    counts = Counter(_tokenize(text))
    return [term for term, _ in counts.most_common(limit)]


def _infer_category(text):
    tokens = set(_tokenize(text))
    if not tokens:
        return ""

    best_category = ""
    best_score = 0
    for category, hints in CATEGORY_HINTS.items():
        score = len(tokens & hints)
        if score > best_score:
            best_category = category
            best_score = score
    return best_category


def _build_document(row, category):
    shoe_name = _normalize_text(row.get("shoe_name"))
    positive_text = _normalize_text(row.get("positive_text"))
    negative_text = _normalize_text(row.get("negative_text"))

    search_text = " ".join(
        part
        for part in [
            shoe_name,
            category,
            positive_text,
            positive_text,
            negative_text,
        ]
        if part
    )
    tokens = _tokenize(search_text)
    token_counts = Counter(tokens)

    return {
        "id": re.sub(r"[^a-z0-9]+", "-", shoe_name.lower()).strip("-"),
        "shoe_name": shoe_name,
        "category": category,
        "positive_text": positive_text,
        "negative_text": negative_text,
        "sample_reviews": [text for text in [positive_text, negative_text] if text][:2],
        "footlocker_url": row.get("url", ""),
        "review_count": len([text for text in [positive_text, negative_text] if text]),
        "top_terms": _top_terms(search_text),
        "token_counts": token_counts,
    }


def load_catalog():
    global catalog_cache
    if catalog_cache is not None:
        return catalog_cache

    grouped = {}
    for category, filename in DATASETS.items():
        path = os.path.join(_data_dir(), filename)
        if not os.path.exists(path):
            continue

        with open(path, newline="", encoding="utf-8-sig") as csv_file:
            for row in csv.DictReader(csv_file):
                shoe_name = _normalize_text(row.get("shoe_name"))
                if not shoe_name:
                    continue

                key = (category, shoe_name.lower())
                positive_text = _normalize_text(row.get("positive_text"))
                negative_text = _normalize_text(row.get("negative_text"))

                if key not in grouped:
                    grouped[key] = {
                        "shoe_name": shoe_name,
                        "url": row.get("url", ""),
                        "positive_texts": [],
                        "negative_texts": [],
                    }

                if positive_text:
                    grouped[key]["positive_texts"].append(positive_text)
                if negative_text:
                    grouped[key]["negative_texts"].append(negative_text)

    catalog = []
    for (category, _), row in grouped.items():
        catalog.append(
            _build_document(
                {
                    "shoe_name": row["shoe_name"],
                    "url": row["url"],
                    "positive_text": " ".join(row["positive_texts"]),
                    "negative_text": " ".join(row["negative_texts"]),
                },
                category,
            )
        )
    catalog_cache = catalog
    return catalog_cache


def _idf_values():
    global idf_cache
    if idf_cache is not None:
        return idf_cache

    catalog = load_catalog()
    doc_count = len(catalog)
    document_frequency = Counter()
    for shoe in catalog:
        document_frequency.update(shoe["token_counts"].keys())

    idf = {}
    for token, frequency in document_frequency.items():
        idf[token] = math.log((1 + doc_count) / (1 + frequency)) + 1.0
    idf_cache = idf
    return idf_cache


def _indexed_catalog():
    global indexed_catalog_cache
    if indexed_catalog_cache is not None:
        return indexed_catalog_cache

    idf = _idf_values()
    indexed = []
    for shoe in load_catalog():
        vector = {}
        for token, count in shoe["token_counts"].items():
            vector[token] = count * idf[token]

        indexed.append({**shoe, "tfidf_vector": vector, "vector_norm": math.sqrt(sum(weight * weight for weight in vector.values()))})
    indexed_catalog_cache = indexed
    return indexed_catalog_cache


def _make_query_vector(query_text):
    counts = Counter(_tokenize(query_text))
    idf = _idf_values()
    vector = {}
    for token, count in counts.items():
        if token in idf:
            vector[token] = count * idf[token]

    norm = math.sqrt(sum(weight * weight for weight in vector.values()))
    return vector, norm


def _cosine_similarity(query_vector, query_norm, document_vector, document_norm):
    if not query_vector or not query_norm or not document_norm:
        return 0.0

    dot_product = sum(
        query_vector[token] * document_vector.get(token, 0.0)
        for token in query_vector
    )
    return dot_product / (query_norm * document_norm)


def _match_reasons(query_vector, shoe, category_filter):
    reasons = []

    if category_filter and shoe["category"] == category_filter:
        reasons.append(f"matches {category_filter} category")

    shared_terms = [
        token for token in query_vector if token in shoe["tfidf_vector"]
    ]
    shared_terms.sort(
        key=lambda token: query_vector[token] * shoe["tfidf_vector"][token],
        reverse=True,
    )

    for token in shared_terms[:3]:
        reasons.append(f"matched '{token}'")

    if not reasons:
        reasons.append("general text similarity")
    return reasons


def search_shoes(query="", category="", use_case="", limit=12):
    category_filter = _normalize_category(category)
    if not category_filter:
        category_filter = _infer_category(f"{query} {use_case}")

    query_text = " ".join(part for part in [query, use_case, category_filter] if part)
    query_vector, query_norm = _make_query_vector(query_text)

    results = []
    for shoe in _indexed_catalog():
        if category_filter and shoe["category"] != category_filter:
            continue

        similarity = _cosine_similarity(
            query_vector,
            query_norm,
            shoe["tfidf_vector"],
            shoe["vector_norm"],
        )
        if similarity <= 0:
            continue

        results.append(
            {
                "id": shoe["id"],
                "shoe_name": shoe["shoe_name"],
                "category": shoe["category"],
                "match_score": round(similarity * 100, 1),
                "review_count": shoe["review_count"],
                "signature_player": None,
                "review_signals": {},
                "top_terms": shoe["top_terms"],
                "match_reasons": _match_reasons(query_vector, shoe, category_filter),
                "sample_reviews": shoe["sample_reviews"],
                "footlocker_url": shoe["footlocker_url"],
                "specs": {},
            }
        )

    results.sort(key=lambda item: (-item["match_score"], item["shoe_name"]))
    results = results[:limit]

    return {
        "results": results,
        "applied_filters": {
            "query": query,
            "category": category_filter,
            "use_case": use_case,
            "requested_attributes": [],
        },
    }
