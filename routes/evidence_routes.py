from flask import Blueprint, jsonify, request

from database.db import get_db
from services import evidence_service as es

bp = Blueprint("evidence", __name__, url_prefix="/api/evidence")


@bp.get("")
def list_all():
    return jsonify({"items": es.list_evidence(get_db())})


@bp.post("")
def create():
    cid = (request.get_json(silent=True) or {}).get("candidate_id")
    if not isinstance(cid, int):
        return jsonify({"error": "candidate_id (integer) is required"}), 400
    return jsonify(es.create_evidence(get_db(), cid)), 201


@bp.get("/<eid>")
def detail(eid):
    db = get_db()
    ev = es.get_evidence(db, eid)
    if ev is None:
        return jsonify({"error": "Evidence not found"}), 404
    ev["history"] = es.verification_history(db, eid)
    return jsonify(ev)


@bp.post("/<eid>/verify")
def verify(eid):
    return jsonify(es.verify_evidence(get_db(), eid))
