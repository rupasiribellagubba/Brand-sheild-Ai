import re

from services.common import ValidationError, log_activity, now_iso

DEMO_BRAND = {
    "name": "NovaPay",
    "description": "NovaPay is a digital wallet for fast, secure payments and money transfers.",
    "website": "https://www.novapay.example",
    "social_handles": "novapay, novapay_help",
    "app_name": "NovaPay Wallet",
    "app_id": "com.novapay.wallet",
    "developer": "NovaPay Technologies Ltd",
}


def parse_handles(value):
    items = value if isinstance(value, list) else re.split(r"[,\n;]+", value or "")
    out = []
    for h in items:
        h = str(h).strip()
        if ":" in h and not h.startswith("http"):
            h = h.split(":", 1)[1]
        h = h.strip().lstrip("@").lower()
        if h and h not in out:
            out.append(h)
    return out


def _row(r):
    if r is None:
        return None
    d = dict(r)
    d["handles"] = parse_handles(d.get("social_handles"))
    return d


def get_brand(db):
    return _row(db.execute("SELECT * FROM brand_profile WHERE id = 1").fetchone())


def save_brand(db, data):
    errors = []
    name = (data.get("name") or "").strip()
    if not name:
        errors.append("Brand name is required.")
    if len(name) > 120:
        errors.append("Brand name must be at most 120 characters.")
    website = (data.get("website") or "").strip()
    if website and not re.match(r"^https?://[^\s/]+\.[^\s/]+", website):
        errors.append("Website must be a valid http(s) URL.")
    handles = parse_handles(data.get("social_handles"))
    if len(handles) > 20:
        errors.append("At most 20 official handles allowed.")
    if errors:
        raise ValidationError("Invalid brand profile", errors)
    vals = (
        name, (data.get("description") or "").strip()[:2000], website, ", ".join(handles),
        (data.get("app_name") or "").strip()[:120], (data.get("app_id") or "").strip()[:200],
        (data.get("developer") or "").strip()[:200], now_iso(),
    )
    db.execute(
        """INSERT INTO brand_profile (id, name, description, website, social_handles, app_name, app_id, developer, updated_at)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=excluded.description,
             website=excluded.website, social_handles=excluded.social_handles, app_name=excluded.app_name,
             app_id=excluded.app_id, developer=excluded.developer, updated_at=excluded.updated_at""",
        vals,
    )
    log_activity(db, f"Brand profile saved: {name}")
    db.commit()
    return get_brand(db)
