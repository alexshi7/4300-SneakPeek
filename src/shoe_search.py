import csv
import math
import os
import re
from collections import Counter

import numpy as np


DATASETS = {
    "basketball": "data/basketball_data.csv",
    "running": "data/running_data.csv",
    "sneakers": "data/sneakers_data2.csv",
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
    "wear",
    "me",
    "my",
    "of",
    "on",
    "or",
    "lifestyle",
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

FL_REVIEWS_PATH = "data/footlocker_reviews_cleaned.csv"
FL_SVD_K = 20        # latent dimensions
FL_SVD_WEIGHT = 0.25  # blend weight: final = (1-w)*tfidf + w*svd
NEG_PENALTY = 0.5    # β: sim_expert = sim_pos - β * sim_neg, clamped ≥ 0

_FL_SVD_UNAVAILABLE = object()  # sentinel distinct from None

catalog_cache = None
idf_cache = None
indexed_catalog_cache = None
fl_svd_cache = None  # None = not yet loaded; _FL_SVD_UNAVAILABLE = failed/missing


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
    # Use raw words (no stop-word filter) so category hint words like
    # "lifestyle" are recognized even though they're in STOP_WORDS.
    tokens = set(TOKEN_RE.findall((text or "").lower()))
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

    # Positive side: shoe name + category + positive text (2x weight)
    pos_text = " ".join(part for part in [shoe_name, category, positive_text, positive_text] if part)
    pos_token_counts = Counter(_tokenize(pos_text))

    # Negative side: only the negative review text
    neg_token_counts = Counter(_tokenize(negative_text))

    return {
        "id": re.sub(r"[^a-z0-9]+", "-", shoe_name.lower()).strip("-"),
        "shoe_name": shoe_name,
        "category": category,
        "positive_text": positive_text,
        "negative_text": negative_text,
        "sample_reviews": [text for text in [positive_text, negative_text] if text][:2],
        "footlocker_url": row.get("url", ""),
        "review_count": len([text for text in [positive_text, negative_text] if text]),
        "top_terms": _top_terms(pos_text),
        "token_counts": pos_token_counts,
        "neg_token_counts": neg_token_counts,
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
        pos_vector = {token: count * idf[token] for token, count in shoe["token_counts"].items()}
        neg_vector = {token: count * idf.get(token, 0) for token, count in shoe["neg_token_counts"].items() if token in idf}

        indexed.append({
            **shoe,
            "tfidf_vector": pos_vector,
            "vector_norm": math.sqrt(sum(w * w for w in pos_vector.values())),
            "neg_tfidf_vector": neg_vector,
            "neg_vector_norm": math.sqrt(sum(w * w for w in neg_vector.values())),
        })
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


def _load_fl_svd():
    """
    Build an LSA model from Foot Locker reviews for lifestyle/sneakers shoes.

    Returns a dict with shoe SVD vectors and projection matrices, or None if
    the data file is missing or there are too few shoes to decompose.
    """
    global fl_svd_cache
    if fl_svd_cache is not None:
        return None if fl_svd_cache is _FL_SVD_UNAVAILABLE else fl_svd_cache

    path = os.path.join(_data_dir(), FL_REVIEWS_PATH)
    if not os.path.exists(path):
        fl_svd_cache = _FL_SVD_UNAVAILABLE
        return None

    sneakers_shoes = {
        doc["shoe_name"].lower()
        for doc in load_catalog()
        if doc["category"] == "sneakers"
    }

    # Aggregate review tokens per shoe (normalize by total tokens to handle
    # unequal review counts — shoes with more reviews won't dominate)
    shoe_tokens = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = _normalize_text(row.get("shoe_name", "")).lower()
            if name not in sneakers_shoes:
                continue
            tokens = _tokenize(row.get("clean_review_text", ""))
            if name not in shoe_tokens:
                shoe_tokens[name] = Counter()
            shoe_tokens[name].update(tokens)

    if len(shoe_tokens) < 2:
        fl_svd_cache = _FL_SVD_UNAVAILABLE
        return None

    vocab = sorted({tok for counts in shoe_tokens.values() for tok in counts})
    vocab_idx = {tok: i for i, tok in enumerate(vocab)}
    n_terms = len(vocab)
    shoes = sorted(shoe_tokens.keys())
    n_shoes = len(shoes)

    # Build TF matrix (n_shoes × n_terms); divide by total tokens per shoe
    A = np.zeros((n_shoes, n_terms))
    for si, name in enumerate(shoes):
        counts = shoe_tokens[name]
        total = sum(counts.values())
        for tok, cnt in counts.items():
            A[si, vocab_idx[tok]] = cnt / total

    # IDF over the Foot Locker corpus
    doc_freq = (A > 0).sum(axis=0)
    idf = np.log((1 + n_shoes) / (1 + doc_freq)) + 1.0
    A = A * idf

    # L2-normalize each shoe row so all shoes contribute equally
    row_norms = np.linalg.norm(A, axis=1, keepdims=True)
    row_norms[row_norms == 0] = 1.0
    A = A / row_norms

    # Truncated SVD
    U, s, Vt = np.linalg.svd(A, full_matrices=False)
    k = min(FL_SVD_K, len(s))
    U_k = U[:, :k]
    s_k = s[:k]
    Vt_k = Vt[:k, :]

    # Shoe embeddings: scale by singular values, then unit-normalize
    shoe_vecs = U_k * s_k
    sv_norms = np.linalg.norm(shoe_vecs, axis=1, keepdims=True)
    sv_norms[sv_norms == 0] = 1.0
    shoe_vecs = shoe_vecs / sv_norms  # (n_shoes, k) unit vectors

    fl_svd_cache = {
        "shoes": shoes,
        "shoe_vecs": shoe_vecs,
        "Vt_k": Vt_k,
        "s_k": s_k,
        "vocab_idx": vocab_idx,
        "idf": idf,
    }
    return fl_svd_cache


def _fl_svd_similarities(query_text):
    """
    Project query_text into the Foot Locker SVD latent space and return
    cosine similarities to each shoe. Returns {} if the model is unavailable
    or the query has no overlap with the FL vocabulary.
    """
    model = _load_fl_svd()
    if model is None:
        return {}

    vocab_idx = model["vocab_idx"]
    idf = model["idf"]
    n_terms = len(vocab_idx)

    counts = Counter(_tokenize(query_text))
    q = np.zeros(n_terms)
    for tok, cnt in counts.items():
        idx = vocab_idx.get(tok)
        if idx is not None:
            q[idx] = cnt * idf[idx]

    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return {}
    q = q / q_norm

    # Fold query into SVD space: q_svd = q @ Vt_k.T / s_k
    q_svd = (q @ model["Vt_k"].T) / (model["s_k"] + 1e-9)
    q_svd_norm = np.linalg.norm(q_svd)
    if q_svd_norm == 0:
        return {}
    q_svd = q_svd / q_svd_norm

    # shoe_vecs are already unit-normalized → dot product = cosine similarity
    sims = np.clip(model["shoe_vecs"] @ q_svd, 0.0, 1.0)
    return {name: float(sims[i]) for i, name in enumerate(model["shoes"])}


def search_shoes(query="", category="", use_case="", limit=12):
    category_filter = _normalize_category(category)
    if not category_filter:
        category_filter = _infer_category(f"{query} {use_case}")

    query_text = " ".join(part for part in [query, use_case, category_filter] if part)
    query_vector, query_norm = _make_query_vector(query_text)

    # Pre-compute Foot Locker SVD similarities for lifestyle/sneakers queries
    fl_sims = {}
    if category_filter == "sneakers":
        fl_sims = _fl_svd_similarities(query_text)

    results = []
    for shoe in _indexed_catalog():
        if category_filter and shoe["category"] != category_filter:
            continue

        pos_sim = _cosine_similarity(
            query_vector,
            query_norm,
            shoe["tfidf_vector"],
            shoe["vector_norm"],
        )
        if pos_sim <= 0:
            continue

        # Penalize if query terms appear in the negative review text
        neg_sim = _cosine_similarity(
            query_vector,
            query_norm,
            shoe["neg_tfidf_vector"],
            shoe["neg_vector_norm"],
        )
        tfidf_sim = max(0.0, pos_sim - NEG_PENALTY * neg_sim)
        if tfidf_sim <= 0:
            continue

        # Blend in Foot Locker SVD signal when available for this shoe
        fl_sim = fl_sims.get(shoe["shoe_name"].lower())
        if fl_sim is not None:
            final_sim = (1 - FL_SVD_WEIGHT) * tfidf_sim + FL_SVD_WEIGHT * fl_sim
        else:
            final_sim = tfidf_sim

        results.append(
            {
                "id": shoe["id"],
                "shoe_name": shoe["shoe_name"],
                "category": shoe["category"],
                "match_score": round(final_sim * 100, 1),
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
