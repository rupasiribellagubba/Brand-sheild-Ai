from flask import jsonify, request

from database.db import get_db
from services import monitor_service as ms


def register(bp, kind):
    """Attach list / create / CSV-import endpoints for one candidate kind."""

    @bp.get("/candidates")
    def list_items():
        items = ms.list_candidates(
            get_db(), kind=kind, q=request.args.get("q", "").strip(), level=request.args.get("level", ""),
            status=request.args.get("status", ""), sort=request.args.get("sort", "score_desc"))
        return jsonify({"items": items, "count": len(items)})

    @bp.post("/candidates")
    def create_item():
        db = get_db()
        cid = ms.add_candidate(db, kind, request.get_json(silent=True) or {})
        return jsonify(ms.get_candidate(db, cid)), 201

    @bp.post("/import")
    def import_items():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"error": "No file uploaded."}), 400
        if not f.filename.lower().endswith(".csv"):
            return jsonify({"error": "Only .csv files are accepted."}), 400
        try:
            text = f.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return jsonify({"error": "File must be UTF-8 encoded text."}), 400
        return jsonify(ms.import_csv(get_db(), kind, text))
