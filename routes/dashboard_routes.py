from flask import Blueprint, jsonify, render_template

from database.db import get_db
from services import blockchain_service, brand_service, monitor_service

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def dashboard():
    return render_template("dashboard.html")


@bp.get("/brand")
def brand_page():
    return render_template("brand_profile.html")


@bp.get("/social")
def social_page():
    return render_template("social_monitor.html")


@bp.get("/apps")
def apps_page():
    return render_template("app_monitor.html")


@bp.get("/candidate/<int:cid>")
def candidate_page(cid):
    return render_template("candidate_detail.html", cid=cid)


@bp.get("/evidence")
def evidence_page():
    return render_template("evidence_vault.html")


@bp.get("/api/dashboard")
def stats():
    db = get_db()
    items = monitor_service.list_candidates(db)
    count = lambda pred: sum(1 for i in items if pred(i))  # noqa: E731
    ev = [dict(r) for r in db.execute(
        """SELECT e.evidence_id, (SELECT result FROM verifications v WHERE v.evidence_id = e.evidence_id
           ORDER BY v.id DESC LIMIT 1) AS last FROM evidence e""")]
    return jsonify({
        "brand": brand_service.get_brand(db),
        "total": len(items),
        "levels": {lv: count(lambda i, lv=lv: i["level"] == lv) for lv in ("High", "Medium", "Low")},
        "social": {"total": count(lambda i: i["kind"] == "social"),
                   "high": count(lambda i: i["kind"] == "social" and i["level"] == "High")},
        "apps": {"total": count(lambda i: i["kind"] == "app"),
                 "high": count(lambda i: i["kind"] == "app" and i["level"] == "High")},
        "statuses": {s: count(lambda i, s=s: i["status"] == s)
                     for s in ("New", "Under Review", "Confirmed Suspicious", "False Positive")},
        "sample_records": count(lambda i: i["is_sample"]),
        "evidence": {"total": len(ev), "intact": sum(1 for e in ev if e["last"] == "intact"),
                     "tampered": sum(1 for e in ev if e["last"] == "tampered"),
                     "unverified": sum(1 for e in ev if e["last"] is None)},
        "blockchain": blockchain_service.status(),
        "activity": [dict(r) for r in db.execute("SELECT message, created_at FROM activity ORDER BY id DESC LIMIT 10")],
    })


@bp.post("/api/demo/seed")
def seed():
    return jsonify(monitor_service.seed_demo(get_db()))
