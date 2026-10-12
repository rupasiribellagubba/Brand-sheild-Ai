"""Shared logic for social-media and app candidates."""
import csv
import io
import json
import re
from pathlib import Path

import config
from services import brand_service, risk_engine
from services.common import ValidationError, log_activity, now_iso

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
MAX_CSV_ROWS = 1000
REQUIRED_COLUMNS = {"social": ["name", "username", "platform"], "app": ["name"]}
FIELDS = {
    "social": ["name", "username", "platform", "url", "description"],
    "app": ["name", "developer", "app_id", "source", "url", "description"],
}
SORTS = {
    "score_desc": "COALESCE(a.score, -1) DESC, c.id DESC",
    "score_asc": "COALESCE(a.score, -1) ASC, c.id DESC",
    "newest": "c.id DESC",
    "name": "c.name COLLATE NOCASE ASC",
}


def validate_candidate(kind, data):
    clean = {f: str(data.get(f) or "").strip() for f in FIELDS[kind]}
    errors = []
    if not clean["name"]:
        errors.append("Name is required.")
    if kind == "social":
        for f in ("username", "platform"):
            if not clean[f]:
                errors.append(f"{f.capitalize()} is required.")
    if clean.get("url") and not re.match(r"^(https?://)?[^\s/]+\.[^\s/]+\S*$", clean["url"]):
        errors.append("URL looks invalid.")
    limits = {"name": 200, "username": 100, "platform": 50, "url": 500, "description": 2000,
              "developer": 200, "app_id": 200, "source": 100}
    for f, v in clean.items():
        if len(v) > limits.get(f, 200):
            errors.append(f"{f} is too long (max {limits.get(f, 200)}).")
    if errors:
        raise ValidationError("Invalid candidate", errors)
    if kind == "app" and not clean["source"]:
        clean["source"] = "Manual entry"
    return clean


def _candidate_dict(row):
    d = dict(row)
    d["indicators"] = json.loads(d["indicators"]) if d.get("indicators") else []
    d["notes"] = json.loads(d["notes"]) if d.get("notes") else []
    return d


def add_candidate(db, kind, data, is_sample=0, commit=True):
    c = validate_candidate(kind, data)
    cur = db.execute(
        """INSERT INTO candidates (kind, name, username, platform, url, description, developer, app_id,
           source, status, is_sample, created_at) VALUES (?,?,?,?,?,?,?,?,?, 'New', ?, ?)""",
        (kind, c["name"], c.get("username", ""), c.get("platform", ""), c.get("url", ""),
         c.get("description", ""), c.get("developer", ""), c.get("app_id", ""),
         c.get("source") or ("Sample data" if is_sample else "Manual entry"), int(is_sample), now_iso()),
    )
    cid = cur.lastrowid
    analyze_candidate(db, cid, commit=False)
    log_activity(db, f"{kind.title()} candidate added: {c['name']}")
    if commit:
        db.commit()
    return cid


def analyze_candidate(db, cid, commit=True):
    row = db.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
    if row is None:
        raise LookupError("Candidate not found")
    cand = dict(row)
    result = risk_engine.analyze(cand["kind"], cand, brand_service.get_brand(db))
    db.execute(
        "INSERT INTO assessments (candidate_id, score, level, indicators, notes, created_at) VALUES (?,?,?,?,?,?)",
        (cid, result["score"], result["level"], json.dumps(result["indicators"]),
         json.dumps(result["notes"]), now_iso()),
    )
    if commit:
        db.commit()
    return result


def reanalyze_all(db):
    ids = [r["id"] for r in db.execute("SELECT id FROM candidates")]
    for cid in ids:
        analyze_candidate(db, cid, commit=False)
    log_activity(db, f"Re-analyzed {len(ids)} candidates")
    db.commit()
    return len(ids)


_BASE = """SELECT c.*, a.id AS assessment_id, a.score, a.level, a.indicators, a.notes, a.summary, a.summary_source
           FROM candidates c LEFT JOIN assessments a
           ON a.id = (SELECT MAX(id) FROM assessments WHERE candidate_id = c.id)"""


def list_candidates(db, kind=None, q="", level="", status="", sort="score_desc"):
    where, params = [], []
    if kind:
        where.append("c.kind = ?"); params.append(kind)
    if q:
        like = f"%{q}%"
        where.append("(c.name LIKE ? OR c.username LIKE ? OR c.developer LIKE ? OR c.app_id LIKE ? OR c.description LIKE ?)")
        params += [like] * 5
    if level in ("Low", "Medium", "High"):
        where.append("a.level = ?"); params.append(level)
    if status in config.VALID_STATUSES:
        where.append("c.status = ?"); params.append(status)
    sql = _BASE + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY " + SORTS.get(sort, SORTS["score_desc"])
    return [_candidate_dict(r) for r in db.execute(sql, params).fetchall()]


def get_candidate(db, cid):
    row = db.execute(_BASE + " WHERE c.id = ?", (cid,)).fetchone()
    return _candidate_dict(row) if row else None


def update_status(db, cid, status):
    if status not in config.VALID_STATUSES:
        raise ValidationError("Invalid status", [f"Status must be one of: {', '.join(config.VALID_STATUSES)}"])
    cur = db.execute("UPDATE candidates SET status = ? WHERE id = ?", (status, cid))
    if cur.rowcount == 0:
        raise LookupError("Candidate not found")
    name = db.execute("SELECT name FROM candidates WHERE id = ?", (cid,)).fetchone()["name"]
    log_activity(db, f"Status of '{name}' set to {status}")
    db.commit()


def import_csv(db, kind, text, is_sample=0):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS[kind] if c not in headers]
    if not headers or missing:
        raise ValidationError("CSV header invalid", [f"Missing required column(s): {', '.join(missing) or 'header row'}. "
                                                    f"Expected columns: {', '.join(FIELDS[kind])}"])
    imported, errors = 0, []
    for n, raw in enumerate(reader, start=2):
        if n - 1 > MAX_CSV_ROWS:
            errors.append({"row": n, "error": f"Row limit of {MAX_CSV_ROWS} exceeded; remaining rows skipped."})
            break
        row = {(k or "").strip().lower(): v for k, v in raw.items() if k}
        if is_sample:
            row["source"] = "Sample data"
        elif kind == "app" and not (row.get("source") or "").strip():
            row["source"] = "CSV import"
        try:
            add_candidate(db, kind, row, is_sample=is_sample, commit=False)
            imported += 1
        except ValidationError as e:
            errors.append({"row": n, "error": "; ".join(e.details)})
    log_activity(db, f"CSV import ({kind}): {imported} imported, {len(errors)} rejected")
    db.commit()
    return {"imported": imported, "skipped": len(errors), "errors": errors}


def seed_demo(db):
    """Load the labelled SAMPLE brand + records (idempotent). Not live monitoring."""
    if db.execute("SELECT 1 FROM candidates WHERE is_sample = 1 LIMIT 1").fetchone():
        return {"seeded": False, "message": "Sample data already loaded."}
    if not brand_service.get_brand(db):
        brand_service.save_brand(db, brand_service.DEMO_BRAND)
    out = {"seeded": True}
    for kind, fname in (("social", "social_candidates.csv"), ("app", "app_candidates.csv")):
        text = (SAMPLE_DIR / fname).read_text(encoding="utf-8")
        out[kind] = import_csv(db, kind, text, is_sample=1)["imported"]
    return out
