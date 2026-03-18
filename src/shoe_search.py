import csv
import os
import re
from collections import Counter, defaultdict
from functools import lru_cache


ATTRIBUTE_PATTERNS = {
    "lightweight": [r"\blightweight\b", r"\blight\b", r"\blighter\b", r"\bnot heavy\b"],
    "traction": [r"\btraction\b", r"\bgrip\b", r"\bgrippy\b", r"\bslip resistant\b", r"\bstability\b"],
    "stylish": [r"\bstylish\b", r"\bstyle\b", r"\blooks great\b", r"\blook great\b", r"\bfashionable\b", r"\btrendy\b", r"\bcute\b", r"\bcolorway\b"],
    "comfort": [r"\bcomfortable\b", r"\bcomfort\b", r"\bcomfy\b", r"\bcushion", r"\bsoft\b"],
    "support": [r"\bsupport\b", r"\bsupportive\b", r"\barch support\b", r"\blocked in\b", r"\bsecure\b"],
    "breathability": [r"\bbreathable\b", r"\bmesh\b", r"\bairy\b", r"\bventilat", r"\bkept my feet cool\b"],
    "durability": [r"\bdurable\b", r"\bwell constructed\b", r"\bconstruction\b", r"\bquality\b", r"\bsolid craftsmanship\b"],
    "wide_fit": [r"\bwide\b", r"\broomy\b", r"\bspacious\b", r"\btoe box\b"],
}

ATTRIBUTE_ALIASES = {
    "lightweight": ["lightweight", "light", "lighter", "quick", "speed"],
    "heavyweight": ["heavyweight", "heavy", "heavier"],
    "traction": ["traction", "grip", "grippy", "court grip"],
    "stylish": ["stylish", "style", "fashion", "fashionable", "look", "looks", "trendy"],
    "comfort": ["comfortable", "comfort", "cushion", "soft"],
    "support": ["support", "supportive", "stable", "stability", "ankle support"],
    "breathability": ["breathable", "breathability", "cool", "ventilation"],
    "durability": ["durable", "durability", "quality"],
    "wide_fit": ["wide", "roomy", "spacious"],
    "signature": ["star player", "signature", "player shoe"],
    "budget": ["cheap", "budget", "value", "affordable"],
}

NEGATED_ALIASES = {
    "signature": ["no signature", "not signature", "non signature", "without signature", "not a signature", "no star player", "without a star player"],
    "ankle_support": ["no ankle support", "without ankle support", "minimal ankle support"],
    "heel_tab": ["no heel tab", "no pull tab", "without heel tab", "without pull tab"],
    "breathability": ["not breathable", "low breathability"],
    "support": ["not supportive", "low support"],
}

NUMERIC_PREFERENCE_ALIASES = {
    "audience_score": {"high": ["high audience score", "popular", "high rated", "best rated"], "low": ["low audience score"]},
    "best_price": {"low": ["cheap", "budget", "affordable", "low price", "under"], "high": ["premium", "expensive", "high price"]},
    "weight_oz": {"low": ["lightweight", "light", "lighter"], "high": ["heavyweight", "heavy", "heavier"]},
    "traction_score": {"high": ["traction", "grip", "grippy"], "low": ["low traction"]},
    "breathability_score": {"high": ["breathable", "breathability", "cool"], "low": ["not breathable", "low breathability"]},
    "energy_return": {"high": ["energy return", "bouncy", "responsive"], "low": ["low energy return"]},
    "shock_absorption": {"high": ["shock absorption", "impact protection", "cushioned landing"], "low": ["ground feel", "court feel"]},
    "outsole_durability_mm": {"high": ["outsole durability", "durable outsole"], "low": ["less durable outsole"]},
    "drop_mm": {"high": ["high drop"], "low": ["low drop", "minimal drop"]},
    "heel_stack_mm": {"high": ["high stack", "max cushion", "more cushion"], "low": ["low stack", "court feel", "minimal cushion"]},
    "forefoot_stack_mm": {"high": ["high forefoot stack", "thick forefoot"], "low": ["low forefoot stack", "low forefoot"]},
    "midsole_softness": {"high": ["soft", "soft midsole", "plush"], "low": ["firm", "firm midsole"]},
    "stiffness_n": {"high": ["stiff", "rigid"], "low": ["flexible", "flex", "bendy"]},
    "torsional_rigidity_score": {"high": ["torsional rigidity", "stable twist", "torsion support"], "low": ["flexible torsion", "twisty"]},
    "heel_counter_stiffness_score": {"high": ["heel counter", "heel lockdown", "heel stability"], "low": ["soft heel counter"]},
    "toebox_width_mm": {"high": ["wide toe box", "roomy toe box", "wide toebox"], "low": ["narrow toe box", "narrow toebox"]},
    "midsole_width_forefoot_mm": {"high": ["wide forefoot base", "stable forefoot"], "low": ["narrow forefoot base"]},
    "midsole_width_heel_mm": {"high": ["wide heel base", "stable heel"], "low": ["narrow heel base"]},
    "heel_padding_durability_score": {"high": ["heel padding durability", "durable heel padding"], "low": ["weak heel padding"]},
    "toebox_durability_score": {"high": ["toebox durability", "toe box durability", "durable toe box"], "low": ["fragile toe box"]},
    "insole_thickness_mm": {"high": ["thick insole"], "low": ["thin insole"]},
    "outsole_hardness_hc": {"high": ["hard outsole", "hard rubber"], "low": ["soft outsole", "soft rubber"]},
    "outsole_thickness_mm": {"high": ["thick outsole"], "low": ["thin outsole"]},
}

BOOLEAN_PREFERENCE_ALIASES = {
    "signature_player": {"true": ["signature", "star player", "player shoe"], "false": ["no signature", "no star player", "non signature", "without signature"]},
    "ankle_support": {"true": ["ankle support", "supportive ankle"], "false": ["no ankle support", "without ankle support"]},
    "is_lightweight": {"true": ["lightweight", "light"], "false": ["heavyweight", "heavy"]},
    "heel_tab_present": {"true": ["heel tab", "pull tab", "finger loop"], "false": ["no heel tab", "no pull tab", "without heel tab"]},
}

STYLE_PREFERENCE_ALIASES = {
    "top_style": {"Low": ["low top", "low-top"], "Mid": ["mid top", "mid-top"], "High": ["high top", "high-top"]},
    "width_fit": {
        "wide": ["wide fit", "wide foot", "roomy fit"],
        "small": ["runs small", "slightly small", "half size small", "small fit"],
        "true": ["true to size"],
    },
}

CATEGORY_KEYWORDS = {
    "basketball": [
        "basketball",
        "court",
        "hoops",
        "point guard",
        "guard",
        "forward",
        "center",
        "dunk",
        "lebron",
        "jordan",
        "kobe",
        "kyrie",
        "kd",
        "ja",
        "luka",
        "harden",
        "dame",
        "giannis",
        "book",
        "curry",
        "sabrina",
        "trae",
    ],
    "running": ["running", "run", "jog", "training", "walk", "walking", "marathon", "vomero", "pegasus", "asics", "gel", "990", "1906"],
    "lifestyle": ["lifestyle", "casual", "everyday", "retro", "fashion", "outfit", "streetwear"],
}

NEGATIVE_HINTS = {
    "lightweight": ["heavy", "bulky"],
    "traction": ["slippery", "slip"],
    "comfort": ["uncomfortable", "hurt", "pain"],
    "support": ["no arch support", "not supportive"],
    "wide_fit": ["narrow", "tight"],
}

NAME_STOP_WORDS = {"mens", "womens", "shoe", "shoes", "low", "mid", "high", "basketball"}


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _normalize_name(text):
    lowered = (text or "").lower().replace("&", " and ")
    lowered = re.sub(r"\|.*$", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def _name_tokens(text):
    return {token for token in _normalize_name(text).split() if token not in NAME_STOP_WORDS}


def _safe_float(value):
    try:
        if value in ("", None, "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _count_matches(patterns, text):
    lower = text.lower()
    return sum(1 for pattern in patterns if re.search(pattern, lower))


def _infer_category(title, reviews_blob):
    combined = f"{title} {reviews_blob}".lower()
    scores = {category: sum(1 for keyword in keywords if keyword in combined) for category, keywords in CATEGORY_KEYWORDS.items()}
    best_category = max(scores, key=scores.get)
    return best_category if scores[best_category] > 0 else "lifestyle"


def _extract_preferences(text, category):
    lower = (text or "").lower()
    requested = set()
    numeric_preferences = {}
    boolean_preferences = {}
    style_preferences = {}
    for attribute, aliases in ATTRIBUTE_ALIASES.items():
        if any(alias in lower for alias in aliases):
            requested.add(attribute)

    if "heavyweight" in requested:
        requested.discard("lightweight")

    for attribute, aliases in NEGATED_ALIASES.items():
        if any(alias in lower for alias in aliases):
            requested.discard(attribute)

    for field, mapping in NUMERIC_PREFERENCE_ALIASES.items():
        for direction, aliases in mapping.items():
            if any(alias in lower for alias in aliases):
                numeric_preferences[field] = direction

    for field, mapping in BOOLEAN_PREFERENCE_ALIASES.items():
        for desired, aliases in mapping.items():
            if any(alias in lower for alias in aliases):
                boolean_preferences[field] = desired == "true"

    for field, mapping in STYLE_PREFERENCE_ALIASES.items():
        for desired, aliases in mapping.items():
            if any(alias in lower for alias in aliases):
                style_preferences[field] = desired

    if "point guard" in lower or "guard" in lower:
        requested.update({"lightweight", "traction", "support"})
        category = category or "basketball"
    if "tall" in lower:
        requested.update({"support", "comfort"})
    if "star player" in lower:
        requested.add("signature")
    if "cheap" in lower or "budget" in lower or "under" in lower:
        requested.add("budget")

    if "signature" in requested and boolean_preferences.get("signature_player") is False:
        requested.discard("signature")

    if "lightweight" in requested:
        numeric_preferences["weight_oz"] = "low"
        boolean_preferences["is_lightweight"] = True
    if "heavyweight" in requested:
        numeric_preferences["weight_oz"] = "high"
        boolean_preferences["is_lightweight"] = False
    if "traction" in requested:
        numeric_preferences["traction_score"] = "high"
    if "breathability" in requested:
        numeric_preferences["breathability_score"] = "high"
    if "budget" in requested:
        numeric_preferences["best_price"] = "low"
    if "support" in requested:
        boolean_preferences["ankle_support"] = True
        numeric_preferences["torsional_rigidity_score"] = "high"
        numeric_preferences["heel_counter_stiffness_score"] = "high"
    if "signature" in requested:
        boolean_preferences["signature_player"] = True

    inferred_category = category
    if not inferred_category:
        for possible_category, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in lower for keyword in keywords):
                inferred_category = possible_category
                break

    return {
        "category": inferred_category or "",
        "requested_attributes": sorted(requested),
        "numeric_preferences": numeric_preferences,
        "boolean_preferences": boolean_preferences,
        "style_preferences": style_preferences,
    }


@lru_cache(maxsize=1)
def load_review_catalog():
    reviews_path = os.path.join(_project_root(), "footlocker_text_reviews_all_shoes.csv")
    grouped = defaultdict(list)
    with open(reviews_path, newline="", encoding="utf-8") as reviews_file:
        for row in csv.DictReader(reviews_file):
            title = _normalize(row.get("shoe_title"))
            if title:
                grouped[title].append(row)

    catalog = []
    for title, rows in grouped.items():
        reviews = [_normalize(row.get("review_text")) for row in rows if _normalize(row.get("review_text"))]
        reviews_blob = "\n".join(reviews)
        review_signals = {}
        for attribute, patterns in ATTRIBUTE_PATTERNS.items():
            positive_hits = _count_matches(patterns, reviews_blob)
            negative_hits = _count_matches(NEGATIVE_HINTS.get(attribute, []), reviews_blob)
            review_signals[attribute] = max(0, positive_hits - negative_hits)

        top_terms = Counter(
            token
            for review in reviews
            for token in re.findall(r"[a-z]{4,}", review.lower())
            if token not in {"this", "that", "with", "they", "shoe", "shoes", "have", "very"}
        ).most_common(12)

        catalog.append(
            {
                "id": rows[0].get("review_product_id") or title,
                "shoe_name": title.replace(" | Foot Locker", ""),
                "category": _infer_category(title, reviews_blob),
                "review_count": len(reviews),
                "review_signals": review_signals,
                "top_terms": [term for term, _ in top_terms],
                "sample_reviews": reviews[:3],
                "footlocker_url": rows[0].get("footlocker_url", ""),
                "name_tokens": _name_tokens(title),
            }
        )

    return catalog


@lru_cache(maxsize=1)
def load_basketball_specs():
    specs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basketball_specs.csv")
    specs = []
    if not os.path.exists(specs_path):
        return specs

    with open(specs_path, newline="", encoding="utf-8") as specs_file:
        for row in csv.DictReader(specs_file):
            row["name_tokens"] = _name_tokens(row.get("shoe_name"))
            for key in [
                "audience_score",
                "best_price",
                "weight_oz",
                "weight_g",
                "breathability_score",
                "traction_score",
                "energy_return",
                "shock_absorption",
                "outsole_durability_mm",
                "drop_mm",
                "heel_stack_mm",
                "forefoot_stack_mm",
                "midsole_softness",
                "stiffness_n",
                "torsional_rigidity_score",
                "heel_counter_stiffness_score",
                "toebox_width_mm",
                "midsole_width_forefoot_mm",
                "midsole_width_heel_mm",
                "heel_padding_durability_score",
                "toebox_durability_score",
                "insole_thickness_mm",
                "outsole_hardness_hc",
                "outsole_thickness_mm",
            ]:
                row[key] = _safe_float(row.get(key))
            row["ankle_support"] = row.get("ankle_support") == "1"
            row["is_lightweight"] = row.get("is_lightweight") == "1"
            row["heel_tab_present"] = str(row.get("heel_tab", "")).strip() not in {"", "-", "None", "none"}
            specs.append(row)

    return specs


def load_catalog():
    return load_review_catalog()


def _find_review_match(spec_row):
    best = None
    best_score = 0.0
    spec_tokens = spec_row["name_tokens"]
    for review_row in load_review_catalog():
        overlap = len(spec_tokens.intersection(review_row["name_tokens"]))
        if not overlap:
            continue
        denominator = max(len(spec_tokens), len(review_row["name_tokens"]), 1)
        score = overlap / denominator
        if score > best_score:
            best_score = score
            best = review_row
    return best if best_score >= 0.34 else None


@lru_cache(maxsize=1)
def _numeric_ranges():
    ranges = {}
    for field in NUMERIC_PREFERENCE_ALIASES:
        values = [row[field] for row in load_basketball_specs() if row.get(field) is not None]
        if values:
            ranges[field] = (min(values), max(values))
    return ranges


def _normalized_numeric_score(value, field, direction):
    if value is None:
        return 0.0
    low, high = _numeric_ranges().get(field, (None, None))
    if low is None or high is None or high == low:
        return 0.0
    normalized = (value - low) / (high - low)
    return normalized if direction == "high" else 1.0 - normalized


def _basketball_structured_score(spec_row, query_tokens, preferences):
    score = 0.0
    reasons = []
    requested_attributes = preferences["requested_attributes"]
    numeric_preferences = preferences["numeric_preferences"]
    boolean_preferences = preferences["boolean_preferences"]
    style_preferences = preferences["style_preferences"]

    if spec_row.get("audience_score"):
        score += spec_row["audience_score"] / 8.0
        reasons.append(f"audience score {int(spec_row['audience_score'])}")

    weight_map = {
        "audience_score": 12,
        "best_price": 12,
        "weight_oz": 18,
        "traction_score": 18,
        "breathability_score": 10,
        "energy_return": 10,
        "shock_absorption": 10,
        "outsole_durability_mm": 10,
        "drop_mm": 8,
        "heel_stack_mm": 10,
        "forefoot_stack_mm": 8,
        "midsole_softness": 10,
        "stiffness_n": 10,
        "torsional_rigidity_score": 10,
        "heel_counter_stiffness_score": 8,
        "toebox_width_mm": 10,
        "midsole_width_forefoot_mm": 8,
        "midsole_width_heel_mm": 8,
        "heel_padding_durability_score": 8,
        "toebox_durability_score": 8,
        "insole_thickness_mm": 6,
        "outsole_hardness_hc": 6,
        "outsole_thickness_mm": 8,
    }

    label_map = {
        "audience_score": "audience score",
        "best_price": "price",
        "weight_oz": "weight",
        "traction_score": "traction",
        "breathability_score": "breathability",
        "energy_return": "energy return",
        "shock_absorption": "shock absorption",
        "outsole_durability_mm": "outsole durability",
        "drop_mm": "drop",
        "heel_stack_mm": "heel stack",
        "forefoot_stack_mm": "forefoot stack",
        "midsole_softness": "midsole softness",
        "stiffness_n": "stiffness",
        "torsional_rigidity_score": "torsional rigidity",
        "heel_counter_stiffness_score": "heel counter stiffness",
        "toebox_width_mm": "toebox width",
        "midsole_width_forefoot_mm": "forefoot base width",
        "midsole_width_heel_mm": "heel base width",
        "heel_padding_durability_score": "heel padding durability",
        "toebox_durability_score": "toebox durability",
        "insole_thickness_mm": "insole thickness",
        "outsole_hardness_hc": "outsole hardness",
        "outsole_thickness_mm": "outsole thickness",
    }

    for field, direction in numeric_preferences.items():
        value = spec_row.get(field)
        pref_score = _normalized_numeric_score(value, field, direction)
        score += pref_score * weight_map.get(field, 8)
        if value is not None:
            reasons.append(f"{label_map[field]} {'high' if direction == 'high' else 'low'} match ({value})")

    for field, desired in boolean_preferences.items():
        if field == "signature_player":
            actual = bool(spec_row.get("signature_player") and spec_row["signature_player"] != "N/A")
        else:
            actual = bool(spec_row.get(field))
        if actual == desired:
            score += 14 if field == "signature_player" else 10
            if field == "signature_player":
                reasons.append("signature model" if desired else "non-signature model")
            elif field == "heel_tab_present":
                reasons.append("has heel tab" if desired else "no heel tab")
            else:
                reasons.append(field.replace("_", " "))

    for field, desired in style_preferences.items():
        value = str(spec_row.get(field) or "")
        if field == "top_style" and value == desired:
            score += 12
            reasons.append(f"{desired.lower()}-top profile")
        if field == "width_fit":
            lowered = value.lower()
            if desired == "wide" and ("true to size" in lowered or "wide" in lowered):
                score += 10
                reasons.append("accommodating fit")
            elif desired == "small" and "small" in lowered:
                score += 10
                reasons.append("runs small")
            elif desired == "true" and "true to size" in lowered:
                score += 10
                reasons.append("true to size")

    if "point" in query_tokens and "guard" in query_tokens:
        if spec_row.get("top_style") == "Low":
            score += 8
            reasons.append("low-top guard profile")
        if spec_row.get("weight_oz") is not None:
            score += max(0.0, 14.8 - spec_row["weight_oz"]) * 6
        if spec_row.get("traction_score") is not None:
            score += spec_row["traction_score"] * 10

    if "tall" in query_tokens and spec_row.get("ankle_support"):
        score += 6

    return score, reasons


def _review_bonus(review_row, requested_attributes, query_tokens):
    if not review_row:
        return 0.0, [], []

    score = 0.0
    reasons = []
    for attribute in requested_attributes:
        attribute_score = review_row["review_signals"].get(attribute, 0)
        normalized_hits = attribute_score / max(review_row["review_count"], 1)
        if normalized_hits > 0:
            score += normalized_hits * 180
            reasons.append(f"reviews mention {attribute.replace('_', ' ')}")

    token_overlap = len(query_tokens.intersection(set(review_row["top_terms"])))
    score += token_overlap * 2

    return score, reasons, review_row["sample_reviews"][:2]


def _search_basketball_specs(query, use_case, preferences, limit):
    query_tokens = _tokenize(f"{query} {use_case}")
    results = []
    for spec_row in load_basketball_specs():
        score, reasons = _basketball_structured_score(spec_row, query_tokens, preferences)
        review_match = _find_review_match(spec_row)
        review_score, review_reasons, sample_reviews = _review_bonus(review_match, preferences["requested_attributes"], query_tokens)
        total_score = score + review_score
        if total_score <= 0:
            continue

        reasons.extend(review_reasons)
        results.append(
            {
                "id": _normalize_name(spec_row["shoe_name"]),
                "shoe_name": spec_row["shoe_name"],
                "category": "basketball",
                "match_score": round(total_score, 1),
                "review_count": review_match["review_count"] if review_match else 0,
                "signature_player": None if spec_row.get("signature_player") in ("", "N/A") else spec_row.get("signature_player"),
                "review_signals": review_match["review_signals"] if review_match else {key: 0 for key in ATTRIBUTE_PATTERNS},
                "top_terms": review_match["top_terms"][:6] if review_match else [],
                "match_reasons": reasons[:5],
                "sample_reviews": sample_reviews,
                "footlocker_url": review_match["footlocker_url"] if review_match else "",
                "specs": {
                    "price_usd": spec_row.get("best_price"),
                    "weight_oz": spec_row.get("weight_oz"),
                    "traction_score": spec_row.get("traction_score"),
                    "breathability_score": spec_row.get("breathability_score"),
                    "heel_stack_mm": spec_row.get("heel_stack_mm"),
                    "forefoot_stack_mm": spec_row.get("forefoot_stack_mm"),
                    "ankle_support": spec_row.get("ankle_support"),
                    "top_style": spec_row.get("top_style"),
                },
            }
        )

    results.sort(key=lambda item: (-item["match_score"], item["shoe_name"]))
    return results[:limit]


def _search_review_catalog(query, category_filter, use_case, requested_attributes, limit):
    query_tokens = _tokenize(f"{query} {use_case}")
    scored = []
    for shoe in load_review_catalog():
        if category_filter and shoe["category"] != category_filter:
            continue

        searchable = " ".join([shoe["shoe_name"].lower(), shoe["category"], " ".join(shoe["top_terms"]), " ".join(shoe["sample_reviews"]).lower()])
        token_overlap = len(query_tokens.intersection(_tokenize(searchable)))
        score = token_overlap * 3
        reasons = []

        for attribute in requested_attributes:
            attribute_score = shoe["review_signals"].get(attribute, 0)
            normalized_hits = attribute_score / max(shoe["review_count"], 1)
            if normalized_hits > 0:
                score += normalized_hits * 220
                reasons.append(f"reviews mention {attribute.replace('_', ' ')}")

        if category_filter and shoe["category"] == category_filter:
            score += 8
            reasons.append(f"matches {category_filter} category")

        if score <= 0:
            continue

        scored.append(
            {
                "id": shoe["id"],
                "shoe_name": shoe["shoe_name"],
                "category": shoe["category"],
                "match_score": round(score, 1),
                "review_count": shoe["review_count"],
                "signature_player": None,
                "review_signals": shoe["review_signals"],
                "top_terms": shoe["top_terms"][:6],
                "match_reasons": reasons[:4] or ["general text overlap"],
                "sample_reviews": shoe["sample_reviews"][:2],
                "footlocker_url": shoe["footlocker_url"],
                "specs": {},
            }
        )

    scored.sort(key=lambda item: (-item["match_score"], -item["review_count"], item["shoe_name"]))
    return scored[:limit]


def search_shoes(query="", category="", use_case="", limit=12):
    preferences = _extract_preferences(use_case or query, category)
    category_filter = (preferences["category"] or category or "").lower().strip()
    requested_attributes = preferences["requested_attributes"]

    if category_filter == "basketball" and load_basketball_specs():
        results = _search_basketball_specs(query, use_case, preferences, limit)
    else:
        results = _search_review_catalog(query, category_filter, use_case, requested_attributes, limit)

    return {
        "results": results,
        "applied_filters": {
            "query": query,
            "category": category_filter,
            "use_case": use_case,
            "requested_attributes": requested_attributes,
        },
    }
