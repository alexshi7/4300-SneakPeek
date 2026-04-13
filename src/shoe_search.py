import csv
import math
import os
import re
from collections import Counter

import numpy as np


DATASETS = {
    "basketball": "data/basketball_data.csv",
    "running": "data/running_data.csv",
    "sneakers": "data/sneakers_data.csv",
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
NEGATIVE_SECTION_WEIGHTS = {
    "who_should_not_buy": 0.7,
    "cons": 0.45,
}
NEGATIVE_BADGE_THRESHOLD = 0.12

QUERY_ATTRIBUTE_PATTERNS = {
    "lightweight": [
        r"\blightweight\b",
        r"\blighter\b",
        r"\blight\b",
        r"\bquick\b",
        r"\bfast\b",
        r"\bspeed\b",
        r"\bnimble\b",
    ],
    "breathability": [
        r"\bbreathab",
        r"\bairy\b",
        r"\bventilat",
        r"\bcool(?:er)?\b",
        r"\bsummer\b",
    ],
    "support": [
        r"\bsupport",
        r"\bsupportive\b",
        r"\bankle\b",
        r"\bstability\b",
        r"\bstable\b",
        r"\bcontainment\b",
        r"\blockdown\b",
        r"\bsecure\b",
        r"\bhigh[ -]?top\b",
    ],
    "comfort": [
        r"\bcomfort",
        r"\bcomfortable\b",
        r"\bcushion",
        r"\bcushioned\b",
        r"\bsoft\b",
        r"\bplush\b",
        r"\bwalking\b",
        r"\btravel\b",
        r"\ball[ -]?day\b",
        r"\blong runs?\b",
        r"\bdaily miles?\b",
        r"\brecovery\b",
    ],
    "distance": [
        r"\bmarathon\b",
        r"\blong runs?\b",
        r"\blong[- ]distance\b",
        r"\bdistance\b",
        r"\bdaily miles?\b",
        r"\bmileage\b",
    ],
    "traction": [
        r"\btraction\b",
        r"\bgrip\b",
        r"\bgrippy\b",
        r"\bslip resistant\b",
        r"\bdust\b",
    ],
    "durability": [
        r"\bdurable\b",
        r"\bdurability\b",
        r"\btough\b",
        r"\boutsole\b",
        r"\bhard[- ]wearing\b",
        r"\bbeater\b",
    ],
    "outdoor": [
        r"\boutdoor\b",
        r"\brough courts?\b",
        r"\bblacktop\b",
        r"\bgravel\b",
        r"\btrail\b",
        r"\bhiking\b",
        r"\bwet ground\b",
    ],
    "width": [
        r"\bwide\b",
        r"\broomy\b",
        r"\bspacious\b",
        r"\bwide feet\b",
        r"\bbroad feet\b",
        r"\btoe ?box\b",
        r"\btoebox\b",
    ],
    "style": [
        r"\bstyle\b",
        r"\bstylish\b",
        r"\bfashion\b",
        r"\boutfits?\b",
        r"\bretro\b",
        r"\bvintage\b",
        r"\bclean white\b",
        r"\bchunky\b",
        r"\bdad shoe\b",
        r"\by2k\b",
    ],
}

EXPLICIT_QUERY_AVOID_PATTERNS = {
    "lightweight": [
        r"\bnot heavy\b",
        r"\bnot bulky\b",
        r"\bnot clunky\b",
    ],
    "width": [
        r"\bnot narrow\b",
        r"\bnot tight\b",
        r"\bwide feet?\b",
        r"\broomy fit\b",
    ],
    "breathability": [
        r"\bnot hot\b",
        r"\bkeep(?:ing)? .* cool\b",
        r"\bcool[- ]running\b",
    ],
    "comfort": [
        r"\bno break[- ]in\b",
        r"\binstant comfort\b",
        r"\bout of the box\b",
    ],
    "traction": [
        r"\bnot slippery\b",
        r"\bwon't slip\b",
    ],
}

NEGATIVE_ATTRIBUTE_PATTERNS = {
    "lightweight": [
        r"\blighter\b",
        r"\blightweight\b",
        r"\bheavy\b",
        r"\bbulky\b",
        r"\bclunky\b",
        r"\bweight\b",
    ],
    "breathability": [
        r"\bbreathab",
        r"\bcool(?:er)?(?:-running)?\b",
        r"\bventilat",
        r"\bairflow\b",
        r"\bhot\b",
        r"\bwarm\b",
    ],
    "support": [
        r"\bsupport",
        r"\bankle\b",
        r"\bstability\b",
        r"\bstable\b",
        r"\bcontainment\b",
        r"\blockdown\b",
        r"\bheel security\b",
        r"\bupper support\b",
    ],
    "comfort": [
        r"\bcomfort",
        r"\bcomfortable\b",
        r"\bcushion",
        r"\bcushioned\b",
        r"\bwalking\b",
        r"\bstanding\b",
        r"\ball[ -]?day\b",
        r"\bbreak[- ]in\b",
        r"\bfirm\b",
        r"\bharsh\b",
        r"\buncomfortable\b",
        r"\bblister",
        r"\bpain\b",
        r"\bhurt\b",
        r"\blong walks?\b",
        r"\blong runs?\b",
    ],
    "distance": [
        r"\blong runs?\b",
        r"\blong[- ]distance\b",
        r"\bmarathon\b",
        r"\bdistance sessions?\b",
        r"\bdaily miles?\b",
        r"\bhigh speeds? or long distances?\b",
    ],
    "traction": [
        r"\btraction\b",
        r"\bgrip\b",
        r"\bdust(?:-sensitive)?\b",
        r"\bslipper",
        r"\bslip\b",
        r"\bwet surfaces?\b",
    ],
    "durability": [
        r"\bdurable\b",
        r"\bdurability\b",
        r"\boutsole\b",
        r"\bwear\b",
        r"\btear\b",
        r"\bfragile\b",
        r"\bcheap\b",
        r"\bcrease",
        r"\brough\b",
    ],
    "outdoor": [
        r"\boutdoor\b",
        r"\brough courts?\b",
        r"\bblacktop\b",
        r"\bgravel\b",
        r"\btrail\b",
        r"\bhiking\b",
        r"\boutdoor suitability\b",
        r"\boutdoor utility\b",
    ],
    "width": [
        r"\bwide\b",
        r"\broomy\b",
        r"\bnarrow\b",
        r"\btight\b",
        r"\btoe ?box\b",
        r"\btoebox\b",
        r"\bwide[- ]foot",
    ],
    "style": [
        r"\bugly\b",
        r"\bunfinished\b",
        r"\boff\b",
        r"\bodd[- ]looking\b",
    ],
}

STYLE_DESIRE_PATTERNS = {
    "chunky": [
        r"\bchunky\b",
        r"\bdad shoe\b",
    ],
    "clean": [
        r"\bclean\b",
        r"\bwhite\b",
        r"\bsimple\b",
        r"\bminimal\b",
        r"\bpolished\b",
        r"\bbusiness[- ]casual\b",
    ],
    "retro": [
        r"\bretro\b",
        r"\bvintage\b",
        r"\bold[- ]school\b",
        r"\by2k\b",
    ],
}

STYLE_AVOID_PATTERNS = {
    "chunky": [
        r"\bnot (?:a )?chunky\b",
        r"\bnot (?:a )?dad shoe\b",
        r"\bnot bulky\b",
        r"\bnot clunky\b",
        r"\bavoid chunky\b",
        r"\bavoid bulky\b",
    ],
}

STYLE_NEGATIVE_PATTERNS = {
    "chunky": [
        r"\bchunky\b",
        r"\bbulky\b",
        r"\bclunky\b",
    ],
    "polished": [
        r"\bugly\b",
        r"\bcheap\b",
        r"\bunfinished\b",
        r"\bloud\b",
    ],
    "generic": [
        r"\bugly\b",
        r"\bunfinished\b",
    ],
}

BERT_MODEL_NAME = "all-MiniLM-L6-v2"  # 22 MB, 384-dim, fast on CPU
BERT_WEIGHT = 0.4    # blend weight: final = (1-w)*prev_score + w*bert_score
BERT_MIN_SIM = 0.25  # minimum BERT similarity to include a shoe that has no TF-IDF overlap

# Free-form user negation: "I don't like carbon", "hate heavy shoes", "no carbon plate"
# These strip negated terms from the positive query and penalize shoes that match them.
USER_NEG_PENALTY = 1.5   # multiplier against negated-term cosine sim; stronger than NEG_PENALTY
_NEGATION_RE = re.compile(
    r"\b(?:don'?t|do\s+not|doesn'?t|does\s+not|hate|dislike|avoid|without|never)"
    r"(?:\s+(?:like|want|prefer|need|use))?"  # optional bridge word
    r"\s+((?:[a-z]+\s+){0,3}[a-z]+)",         # capture up to 4 words after
    re.IGNORECASE,
)
_NO_NOT_RE = re.compile(
    r"\b(?:no|not)\s+(?:a\s+fan\s+of\s+)?((?:[a-z]+\s+){0,1}[a-z]+)",
    re.IGNORECASE,
)

_FL_SVD_UNAVAILABLE = object()  # sentinel distinct from None
_BERT_UNAVAILABLE = object()

catalog_cache = None
idf_cache = None
indexed_catalog_cache = None
fl_svd_cache = None  # None = not yet loaded; _FL_SVD_UNAVAILABLE = failed/missing
bert_cache = None    # None = not yet loaded; _BERT_UNAVAILABLE = failed/missing


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
    negative_sections = _extract_negative_sections(negative_text)

    # Positive side: shoe name + category + positive text (2x weight)
    pos_text = " ".join(part for part in [shoe_name, category, positive_text, positive_text] if part)
    pos_token_counts = Counter(_tokenize(pos_text))

    # Negative side: only the negative review text
    neg_text = " ".join(
        part for part in [
            negative_sections["who_should_not_buy"],
            negative_sections["cons"],
        ] if part
    )
    neg_token_counts = Counter(_tokenize(neg_text))

    return {
        "id": re.sub(r"[^a-z0-9]+", "-", shoe_name.lower()).strip("-"),
        "shoe_name": shoe_name,
        "category": category,
        "positive_text": positive_text,
        "negative_text": negative_text,
        "negative_sections": negative_sections,
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


def _extract_negative_sections(negative_text):
    text = _normalize_text(negative_text)
    if not text:
        return {"who_should_not_buy": "", "cons": ""}

    who_match = re.search(
        r"Who should not buy:\s*(.+?)(?:Cons?:|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    cons_match = re.search(r"Cons?:\s*(.+)$", text, re.IGNORECASE | re.DOTALL)

    if who_match or cons_match:
        return {
            "who_should_not_buy": _normalize_text(who_match.group(1) if who_match else ""),
            "cons": _normalize_text(cons_match.group(1) if cons_match else ""),
        }

    # Sneakers data usually stores only a concise cons summary with no labels.
    return {"who_should_not_buy": "", "cons": text}


def _matches_any(patterns, text):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _section_match_weight(sections, patterns):
    matched_weight = 0.0
    for section_name, section_weight in NEGATIVE_SECTION_WEIGHTS.items():
        section_text = sections.get(section_name, "")
        if section_text and _matches_any(patterns, section_text):
            matched_weight = max(matched_weight, section_weight)
    return matched_weight


def _style_preferences(query_text):
    lower = (query_text or "").lower()
    return {
        "wants_chunky": _matches_any(STYLE_DESIRE_PATTERNS["chunky"], lower),
        "wants_clean": _matches_any(STYLE_DESIRE_PATTERNS["clean"], lower),
        "wants_retro": _matches_any(STYLE_DESIRE_PATTERNS["retro"], lower),
        "avoids_chunky": _matches_any(STYLE_AVOID_PATTERNS["chunky"], lower),
        "wants_style": bool(
            re.search(r"\bstyle\b|\bstylish\b|\bfashion\b|\boutfits?\b|\blooks? good\b", lower)
        ),
    }


def _style_penalty(query_text, sections):
    prefs = _style_preferences(query_text)
    penalty = 0.0

    if prefs["avoids_chunky"]:
        penalty = max(penalty, _section_match_weight(sections, STYLE_NEGATIVE_PATTERNS["chunky"]))

    if prefs["wants_clean"]:
        penalty = max(penalty, _section_match_weight(sections, STYLE_NEGATIVE_PATTERNS["polished"]))
    elif prefs["wants_style"]:
        penalty = max(penalty, _section_match_weight(sections, STYLE_NEGATIVE_PATTERNS["generic"]))

    # Wanting a chunky or retro style should not be penalized just because a
    # shoe is described as bulky/chunky in its downsides.
    if prefs["wants_chunky"] and penalty and penalty <= NEGATIVE_SECTION_WEIGHTS["cons"]:
        penalty = 0.0

    return penalty


def _requested_penalty_attributes(query_text, category):
    lower = (query_text or "").lower()
    requested = set()

    for attribute, patterns in QUERY_ATTRIBUTE_PATTERNS.items():
        if any(re.search(pattern, lower) for pattern in patterns):
            requested.add(attribute)

    for attribute, patterns in EXPLICIT_QUERY_AVOID_PATTERNS.items():
        if _matches_any(patterns, lower):
            requested.add(attribute)

    if category == "basketball":
        if re.search(r"\bheavy\b.*\bcenter\b|\bcenter\b.*\bheavy\b", lower):
            requested.update({"support", "comfort"})
            requested.discard("lightweight")
        if re.search(r"\bpoint guard\b", lower):
            requested.update({"lightweight", "traction"})

    if category == "running" and re.search(r"\bmarathon\b|\blong runs?\b|\bdaily miles?\b", lower):
        requested.add("distance")

    return requested


def _explicit_avoid_attributes(query_text):
    lower = (query_text or "").lower()
    avoided = set()
    for attribute, patterns in EXPLICIT_QUERY_AVOID_PATTERNS.items():
        if _matches_any(patterns, lower):
            avoided.add(attribute)
    return avoided


def _expert_penalty(query_text, category, shoe):
    requested = _requested_penalty_attributes(query_text, category)
    if not requested:
        return 0.0, []

    explicit_avoids = _explicit_avoid_attributes(query_text)
    attribute_weights = {}
    sections = shoe.get("negative_sections") or _extract_negative_sections(shoe.get("negative_text", ""))

    for attribute in requested:
        if attribute == "style":
            continue
        patterns = NEGATIVE_ATTRIBUTE_PATTERNS.get(attribute, [])
        if not patterns:
            continue
        weight = _section_match_weight(sections, patterns)
        if attribute in explicit_avoids and weight:
            weight = min(1.0, weight + 0.15)
        if weight:
            attribute_weights[attribute] = max(attribute_weights.get(attribute, 0.0), weight)

    if "style" in requested:
        style_weight = _style_penalty(query_text, sections)
        if style_weight:
            attribute_weights["style"] = max(attribute_weights.get("style", 0.0), style_weight)

    if not attribute_weights:
        return 0.0, []

    penalty = min(1.0, sum(attribute_weights.values()) / max(len(requested), 1))
    return penalty, sorted(attribute_weights)


def _expert_penalty_detail(shoe):
    sections = shoe.get("negative_sections") or _extract_negative_sections(shoe.get("negative_text", ""))
    details = []
    who_should_not_buy = sections.get("who_should_not_buy", "")
    cons = sections.get("cons", "")

    if who_should_not_buy:
        details.append(f"Who should not buy: {who_should_not_buy}")
    if cons:
        details.append(f"Cons: {cons}")

    return "\n\n".join(details)


def _query_tags(query_vector, shoe, limit=5):
    """Return the top matched terms between query and this specific shoe, ranked
    by their contribution to the cosine similarity score."""
    shared = [
        (token, query_vector[token] * shoe["tfidf_vector"][token])
        for token in query_vector
        if token in shoe["tfidf_vector"]
    ]
    shared.sort(key=lambda x: x[1], reverse=True)
    tags = [t for t, _ in shared[:limit]]
    # Fall back to the shoe's own top terms if there's no query overlap
    if not tags:
        tags = shoe["top_terms"][:limit]
    return tags


def _review_evidence(query_vector, shoe):
    """Extract a human-readable evidence sentence from the shoe's review text
    that is most relevant to the query."""
    shared = sorted(
        [
            (t, query_vector[t] * shoe["tfidf_vector"][t])
            for t in query_vector
            if t in shoe["tfidf_vector"]
        ],
        key=lambda x: x[1],
        reverse=True,
    )
    top_tokens = {t for t, _ in shared[:6]}

    pos_text = shoe.get("positive_text", "")
    if not pos_text:
        return "Matches based on general review text similarity."

    # Prefer the "Pros:" section when present
    pros_match = re.search(r"Pros?:\s*(.+?)(?:Cons?:|$)", pos_text, re.IGNORECASE | re.DOTALL)
    search_text = pros_match.group(1).strip() if pros_match else pos_text

    # Split into clauses and find the one with the most overlap with the query
    clauses = re.split(r"[,\n]", search_text)
    best_clause = ""
    best_overlap = 0
    for clause in clauses:
        clause = clause.strip()
        if len(clause) < 12:
            continue
        clause_tokens = set(_tokenize(clause))
        overlap = len(clause_tokens & top_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_clause = clause

    if best_clause and best_overlap > 0:
        if len(best_clause) > 110:
            best_clause = best_clause[:110].rsplit(" ", 1)[0] + "\u2026"
        return f'Reviewers highlight: "{best_clause.strip()}"'

    # Fallback: name the top matched terms
    if shared:
        term_list = ", ".join(t for t, _ in shared[:3])
        return f"Review text aligns with: {term_list}"
    return "Matches based on general review text similarity."


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

    #Aaron did the rest of the method here to get the top contributing dimension and its concept words for each shoe, and format the reason string accordingly.
    # Calculate similarities and dimension contributions
    shoe_vecs = model["shoe_vecs"]
    sims = np.clip(shoe_vecs @ q_svd, 0.0, 1.0)
    
    # NEW: Determine WHICH dimension contributed the most to the match
    contributions = shoe_vecs * q_svd
    top_dims = np.argmax(contributions, axis=1)
    
    # Reverse the vocabulary dictionary to look up words
    idx_to_vocab = {idx: tok for tok, idx in vocab_idx.items()}

    fl_results = {}
    for i, name in enumerate(model["shoes"]):
        best_k = top_dims[i]
        row_k = model["Vt_k"][best_k, :]
        
        # If the activation is positive, get the top positive words. If negative, get the most negative.
        if q_svd[best_k] > 0:
            top_indices = np.argsort(row_k)[::-1][:3]
        else:
            top_indices = np.argsort(row_k)[:3]
            
        concept_words = [idx_to_vocab.get(idx, "") for idx in top_indices]
        
        fl_results[name] = {
            "score": float(sims[i]),
            "reason": f"SVD Dim {best_k+1} ({', '.join(concept_words)})"
        }

    return fl_results


def _load_bert_index():
    """
    Encode every shoe's review text with a sentence-transformer model and cache
    the resulting unit-normalized embedding matrix.  Returns None if the
    sentence-transformers library is not installed or encoding fails.
    """
    global bert_cache
    if bert_cache is not None:
        return None if bert_cache is _BERT_UNAVAILABLE else bert_cache

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        bert_cache = _BERT_UNAVAILABLE
        return None

    try:
        model = SentenceTransformer(BERT_MODEL_NAME)
        catalog = _indexed_catalog()

        # Encode shoe_name + category + positive review text for richest context
        texts = [
            f"{shoe['shoe_name']} {shoe['category']} {shoe['positive_text']}"
            for shoe in catalog
        ]
        shoe_ids = [shoe["id"] for shoe in catalog]

        embeddings = model.encode(
            texts,
            normalize_embeddings=True,  # unit vectors → dot product == cosine sim
            show_progress_bar=False,
            batch_size=64,
        )  # shape: (n_shoes, 384)

        bert_cache = {
            "model": model,
            "shoe_ids": shoe_ids,
            "embeddings": embeddings,
        }
        return bert_cache
    except Exception:
        bert_cache = _BERT_UNAVAILABLE
        return None


def _bert_similarities(query_text):
    """
    Encode query_text and return cosine similarity to every shoe as a dict
    {shoe_id: float}.  Returns {} if the BERT index is unavailable.
    """
    index = _load_bert_index()
    if index is None:
        return {}

    q_vec = index["model"].encode(
        [query_text], normalize_embeddings=True
    )[0]  # (384,)

    # Dot product of unit vectors == cosine similarity
    sims = np.clip(index["embeddings"] @ q_vec, 0.0, 1.0)  # (n_shoes,)
    return {shoe_id: float(sim) for shoe_id, sim in zip(index["shoe_ids"], sims)}


def _parse_query(text):
    """
    Split a natural-language query into what the user wants vs. what they
    explicitly don't want.

    Returns:
        positive_text  – original text with negation phrases removed;
                         safe to feed into TF-IDF and BERT.
        negated_tokens – set of IDF-tokenized terms the user rejected
                         (e.g. "I don't like carbon" → {"carbon"}).
    """
    negated_tokens = set()
    cleaned = text

    for pattern in (_NEGATION_RE, _NO_NOT_RE):
        for match in pattern.finditer(text):
            negated_tokens.update(_tokenize(match.group(1)))
            # Blank out the full matched span so it doesn't pollute positive text
            cleaned = cleaned.replace(match.group(0), " ")

    positive_text = re.sub(r"\s+", " ", cleaned).strip()
    return positive_text, negated_tokens


def search_shoes(query="", category="", use_case="", limit=12):
    category_filter = _normalize_category(category)
    if not category_filter:
        category_filter = _infer_category(f"{query} {use_case}")

    full_query_text = " ".join(part for part in [query, use_case, category_filter] if part)

    # Strip negation phrases so "I don't like carbon" doesn't reward carbon shoes.
    # positive_query_text is used for all scoring; negated_tokens drive a separate penalty.
    positive_query_text, negated_tokens = _parse_query(full_query_text)

    requested_attributes = sorted(_requested_penalty_attributes(full_query_text, category_filter))
    query_vector, query_norm = _make_query_vector(positive_query_text)

    # Build a penalty vector from whatever the user explicitly doesn't want
    idf = _idf_values()
    user_neg_vector = {t: idf[t] for t in negated_tokens if t in idf}
    user_neg_norm = math.sqrt(sum(w * w for w in user_neg_vector.values())) if user_neg_vector else 0.0

    # Pre-compute Foot Locker SVD similarities for lifestyle/sneakers queries
    fl_sims = {}
    if category_filter == "sneakers":
        fl_sims = _fl_svd_similarities(positive_query_text)

    # Pre-compute BERT semantic similarities using only what the user wants
    bert_sims = _bert_similarities(positive_query_text)

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
        bert_sim = bert_sims.get(shoe["id"], 0.0)

        # Keep shoe if it has TF-IDF overlap OR strong semantic similarity from BERT.
        # This lets pure-semantic matches (e.g. "plush underfoot" ~ "cushioned") surface
        # even when they share no exact tokens with the query.
        if pos_sim <= 0 and bert_sim < BERT_MIN_SIM:
            continue

        # Penalize only when the negative review text explicitly conflicts
        # with what the user asked for in "Who should not buy" or "Cons".
        neg_sim, penalty_attributes = _expert_penalty(full_query_text, category_filter, shoe)
        tfidf_sim = max(0.0, pos_sim - NEG_PENALTY * neg_sim)

        # Blend in Foot Locker SVD signal ONLY if the shoe has sufficient user reviews
        fl_data = fl_sims.get(shoe["shoe_name"].lower())
        svd_reason = None

        # If the shoe is niche (< 15 reviews), rely completely on the TF-IDF (expert) score
        if fl_data is not None and shoe["review_count"] >= 15:
            fl_sim = fl_data["score"]
            expert_sim = (1 - FL_SVD_WEIGHT) * tfidf_sim + FL_SVD_WEIGHT * fl_sim
            svd_reason = fl_data["reason"]
        else:
            expert_sim = tfidf_sim

        # Blend BERT semantic similarity with the expert (TF-IDF ± SVD) score.
        # BERT catches meaning-level matches; expert score catches term-level precision.
        final_sim = (1 - BERT_WEIGHT) * expert_sim + BERT_WEIGHT * bert_sim

        # Penalize shoes whose positive reviews strongly match what the user said they dislike.
        # e.g. "I don't like carbon" → carbon shoe reviews score high → subtract penalty.
        if user_neg_vector:
            user_neg_sim = _cosine_similarity(
                user_neg_vector, user_neg_norm,
                shoe["tfidf_vector"], shoe["vector_norm"],
            )
            final_sim = max(0.0, final_sim - USER_NEG_PENALTY * user_neg_sim)

        if final_sim <= 0:
            continue
        
        # --- NEW TITLE BOOST LOGIC ---
        # Extract words from the user's search and the shoe's name
        user_words = set(_tokenize(f"{query} {use_case}"))
        name_words = set(_tokenize(shoe["shoe_name"]))
        
        # Find how many words overlap (e.g., "nike dunk" -> 2 overlapping words)
        name_overlap = user_words.intersection(name_words)
        title_boosted = False
        
        # If they matched at least 2 words from the title (or 1 if it's a 1-word shoe brand)
        if len(name_overlap) >= 2 or (len(name_words) == 1 and len(name_overlap) == 1):
            final_sim *= 3.0  # 300% score boost to guarantee top spots!
            title_boosted = True
        # -----------------------------

        # Build special-badge reasons only (no "matched 'X'" keyword clutter)
        special_badges = []
        expert_penalty_detail = ""
        if title_boosted:
            special_badges.append("🎯 Direct Name Match")
        if svd_reason:
            special_badges.append(f"✨ Matches {svd_reason}")
        if neg_sim > NEGATIVE_BADGE_THRESHOLD:
            special_badges.append("⚠️ Expert Penalty Applied")
            expert_penalty_detail = _expert_penalty_detail(shoe)

        results.append(
            {
                "id": shoe["id"],
                "shoe_name": shoe["shoe_name"],
                "category": shoe["category"],
                "match_score": round(final_sim * 100, 1),
                "review_count": shoe["review_count"],
                "signature_player": None,
                "review_signals": {},
                "top_terms": _query_tags(query_vector, shoe),
                "match_reasons": special_badges,
                "expert_penalty_detail": expert_penalty_detail,
                "review_evidence": _review_evidence(query_vector, shoe),
                "sample_reviews": shoe["sample_reviews"],
                "footlocker_url": shoe["footlocker_url"],
                "specs": {},
            }
        )

    results.sort(key=lambda item: (-item["match_score"], item["shoe_name"]))
    results = results[:limit]

    # Normalize scores so the top result = 100% and others are shown relative to it
    if results:
        max_score = results[0]["match_score"]
        if max_score > 0:
            for r in results:
                r["match_score"] = round((r["match_score"] / max_score) * 100, 1)

    return {
        "results": results,
        "applied_filters": {
            "query": query,
            "category": category_filter,
            "use_case": use_case,
            "requested_attributes": requested_attributes,
        },
    }
