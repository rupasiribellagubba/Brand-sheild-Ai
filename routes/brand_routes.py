from flask import Blueprint, jsonify, request

from database.db import get_db
from services import brand_service, monitor_service

bp = Blueprint("brand", __name__, url_prefix="/api/brand")


@bp.get("")
def get_brand():
    return jsonify({"brand": brand_service.get_brand(get_db())})


@bp.route("", methods=["PUT", "POST"])
def save_brand():
    db = get_db()
    brand = brand_service.save_brand(db, request.get_json(silent=True) or {})
    n = monitor_service.reanalyze_all(db)  # keep scores consistent with the new profile
    return jsonify({"brand": brand, "reanalyzed": n})
