"""Explainable, configurable risk engine.

Scores are SIMILARITY SIGNALS, not proof of fraud. Missing data contributes 0
points and is reported as "not scored" rather than treated as malicious.
"""
import re
from urllib.parse import urlparse

import config

try:
    from rapidfuzz import fuzz

    ENGINE = "rapidfuzz"

    def _ratio(a, b):
        return fuzz.ratio(a, b) / 100

    def _tset(a, b):
        return fuzz.token_set_ratio(a, b) / 100

    def _partial(a, b):
        return fuzz.partial_ratio(a, b) / 100

except ImportError:  # graceful fallback so the app runs without RapidFuzz
    from difflib import SequenceMatcher

    ENGINE = "difflib"

    def _ratio(a, b):
        return SequenceMatcher(None, a, b).ratio()

    def _tset(a, b):
        ta, tb = set(a.split()), set(b.split())
        inter = ta & tb
        if not inter:
            return 0.0
        if inter == ta or inter == tb:
            return 1.0
        return 2 * len(inter) / (len(ta) + len(tb))

    def _partial(a, b):
        s, l = sorted((a, b), key=len)
        if len(s) == len(l):
            return _ratio(s, l)
        return max(_ratio(s, l[i:i + len(s)]) for i in range(len(l) - len(s) + 1))


_LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "@": "a", "$": "s"})


def norm(text):
    t = (text or "").lower().translate(_LEET)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def similarity(a, b, partial=True):
    """0..1 similarity or None when either side is missing."""
    a, b = norm(a), norm(b)
    if not a or not b:
        return None
    s = max(_ratio(a, b), _tset(a, b))
    if partial:
        a2, b2 = a.replace(" ", ""), b.replace(" ", "")
        if min(len(a2), len(b2)) >= 4:
            s = max(s, _partial(a2, b2))
    return s


def _shape(s):
    """Map raw similarity so that <=50% counts as no signal."""
    if s is None:
        return None
    return max(0.0, min(1.0, (s - 0.5) / 0.5))


def domain_of(url):
    if not url:
        return ""
    u = url.strip()
    if "://" not in u:
        u = "http://" + u
    host = (urlparse(u).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _label(host):
    parts = host.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else host


def _is_official_domain(host, official):
    return host == official or host.endswith("." + official)


def _terms_found(*texts):
    blob = " " + norm(" ".join(t or "" for t in texts)) + " "
    return sorted({t for t in config.SUSPICIOUS_TERMS if f" {norm(t)} " in blob})


def _ind(key, label, value, weight, detail, available=True):
    value = 0.0 if value is None else float(value)
    return {
        "key": key, "label": label, "weight": weight,
        "value": round(value, 3), "contribution": round(weight * value, 1),
        "available": available, "detail": detail,
    }


def _level(score):
    t = config.RISK_THRESHOLDS
    return "High" if score >= t["high"] else "Medium" if score >= t["medium"] else "Low"


def _finalize(indicators, kind, notes, official_match=False):
    if official_match:
        for i in indicators:
            i["value"], i["contribution"] = 0.0, 0.0
        score = 0
    else:
        total_w = sum(config.RISK_WEIGHTS[kind].values()) or 1
        score = round(sum(i["contribution"] for i in indicators) / total_w * 100)
        score = max(0, min(100, score))
    missing = [i["label"] for i in indicators if not i["available"]]
    if missing and not official_match:
        notes.append("Not scored (data missing, not treated as suspicious): " + ", ".join(missing) + ".")
    notes.append("Similarity signals only - this is not confirmed fraud. Manual review required.")
    return {"score": score, "level": _level(score), "indicators": indicators,
            "notes": notes, "official_match": official_match, "engine": ENGINE}


def _name_ind(w, brand_name, cand_name):
    s = similarity(brand_name, cand_name)
    if s is None:
        return _ind("name_similarity", "Name similarity", 0, w, "Brand or candidate name missing.", False)
    return _ind("name_similarity", "Name similarity", _shape(s), w,
                f"'{cand_name}' vs official '{brand_name}': {round(s * 100)}% similar.")


def _desc_ind(w, brand_desc, cand_desc):
    s = similarity(brand_desc, cand_desc, partial=False)
    if s is None:
        return _ind("description_similarity", "Description similarity", 0, w,
                    "Description missing on one side.", False)
    return _ind("description_similarity", "Description similarity", _shape(s), w,
                f"Description overlaps official text by {round(s * 100)}%.")


def _wording_ind(w, *texts):
    if not any((t or "").strip() for t in texts):
        return _ind("suspicious_wording", "Suspicious wording", 0, w, "No text available.", False)
    found = _terms_found(*texts)
    value = min(1.0, len(found) / 3)
    detail = ("Risky terms found: " + ", ".join(found) + ".") if found else "No risky terms found."
    return _ind("suspicious_wording", "Suspicious wording", value, w, detail)


def analyze_social(c, brand):
    w = config.RISK_WEIGHTS["social"]
    handles = brand.get("handles") or []
    user = (c.get("username") or "").strip().lstrip("@").lower()
    official_match = bool(user) and user in handles
    notes = []

    ind = [_name_ind(w["name_similarity"], brand.get("name"), c.get("name"))]

    sims = [(similarity(h, user), h) for h in handles if user]
    sims = [(s, h) for s, h in sims if s is not None]
    if sims:
        s, h = max(sims)
        ind.append(_ind("username_similarity", "Username vs official handles", _shape(s), w["username_similarity"],
                        f"'@{user}' closest to official '@{h}' ({round(s * 100)}%) but is not an official handle."))
    else:
        ind.append(_ind("username_similarity", "Username vs official handles", 0, w["username_similarity"],
                        "No official handles or no username provided.", False))

    off_dom, cand_dom = domain_of(brand.get("website")), domain_of(c.get("url"))
    if not cand_dom or not off_dom:
        ind.append(_ind("url_lookalike", "URL / domain look-alike", 0, w["url_lookalike"],
                        "Candidate URL or official website missing.", False))
    elif _is_official_domain(cand_dom, off_dom):
        ind.append(_ind("url_lookalike", "URL / domain look-alike", 0, w["url_lookalike"],
                        f"URL points to official domain {off_dom}."))
    else:
        s = similarity(_label(off_dom), _label(cand_dom)) or 0
        ind.append(_ind("url_lookalike", "URL / domain look-alike", _shape(s), w["url_lookalike"],
                        f"Domain '{cand_dom}' differs from official '{off_dom}' ({round(s * 100)}% label similarity)."))

    ind.append(_desc_ind(w["description_similarity"], brand.get("description"), c.get("description")))
    ind.append(_wording_ind(w["suspicious_wording"], c.get("name"), c.get("username"), c.get("description")))

    if official_match:
        notes.append(f"Username '@{user}' matches a registered official handle; treated as the brand's own account.")
    return _finalize(ind, "social", notes, official_match)


def analyze_app(c, brand):
    w = config.RISK_WEIGHTS["app"]
    notes = []
    cid, oid = (c.get("app_id") or "").strip().lower(), (brand.get("app_id") or "").strip().lower()
    official_match = bool(cid and oid and cid == oid)

    name_ind = _name_ind(w["name_similarity"], brand.get("app_name") or brand.get("name"), c.get("name"))
    ind = [name_ind]

    cdev, odev = c.get("developer"), brand.get("developer")
    dsim = similarity(odev, cdev, partial=False)
    if dsim is None:
        ind.append(_ind("developer_mismatch", "Developer / publisher mismatch", 0, w["developer_mismatch"],
                        "Developer missing on one side.", False))
    elif name_ind["value"] < 0.4:
        ind.append(_ind("developer_mismatch", "Developer / publisher mismatch", 0, w["developer_mismatch"],
                        "Name is not similar enough for a developer mismatch to be meaningful."))
    elif dsim >= 0.85:
        ind.append(_ind("developer_mismatch", "Developer / publisher mismatch", 0, w["developer_mismatch"],
                        f"Developer '{cdev}' matches official '{odev}'."))
    else:
        ind.append(_ind("developer_mismatch", "Developer / publisher mismatch", 1 - dsim, w["developer_mismatch"],
                        f"Similar app name but developer '{cdev}' differs from official '{odev}'."))

    s = similarity(oid, cid)
    if s is None:
        ind.append(_ind("app_id_similarity", "App identifier look-alike", 0, w["app_id_similarity"],
                        "Official or candidate app identifier missing.", False))
    else:
        ind.append(_ind("app_id_similarity", "App identifier look-alike", _shape(s), w["app_id_similarity"],
                        f"'{cid}' vs official '{oid}': {round(s * 100)}% similar but not identical."))

    ind.append(_desc_ind(w["description_similarity"], brand.get("description"), c.get("description")))
    ind.append(_wording_ind(w["suspicious_wording"], c.get("name"), c.get("description")))
    if official_match:
        notes.append("App identifier matches the registered official application.")
    return _finalize(ind, "app", notes, official_match)


def analyze(kind, candidate, brand):
    if not brand or not brand.get("name"):
        return {"score": 0, "level": "Low", "indicators": [], "official_match": False, "engine": ENGINE,
                "notes": ["No official brand profile saved yet - create one to enable scoring."]}
    return (analyze_social if kind == "social" else analyze_app)(candidate, brand)
