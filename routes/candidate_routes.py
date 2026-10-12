from flask import Blueprint, jsonify, request

from database.db import get_db
from services import ai_service, evidence_service, monitor_service

bp = Blueprint("candidates", __name__, url_prefix="/api/candidates")


@bp.get("/<int:cid>")
def detail(cid):
    db = get_db()
    cand = monitor_service.get_candidate(db, cid)
    if cand is None:
        return jsonify({"error": "Candidate not found"}), 404
    cand["evidence"] = evidence_service.list_evidence(db, cid)
    return jsonify(cand)


@bp.patch("/<int:cid>/status")
def status(cid):
    monitor_service.update_status(get_db(), cid, (request.get_json(silent=True) or {}).get("status", ""))
    return jsonify({"ok": True})


@bp.post("/<int:cid>/summary")
def summary(cid):
    db = get_db()
    cand = monitor_service.get_candidate(db, cid)
    if cand is None or cand["assessment_id"] is None:
        return jsonify({"error": "Candidate not found"}), 404
    text, source, warning = ai_service.generate_summary(cand, cand)
    db.execute("UPDATE assessments SET summary = ?, summary_source = ? WHERE id = ?", (text, source, cand["assessment_id"]))
    db.commit()
    return jsonify({"summary": text, "source": source, "warning": warning})


@bp.post("/reanalyze")
def reanalyze():
    return jsonify({"reanalyzed": monitor_service.reanalyze_all(get_db())})
