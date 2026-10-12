from flask import Blueprint, jsonify, request

from database.db import get_db
from services import blockchain_service as bs

bp = Blueprint("blockchain", __name__, url_prefix="/api")


@bp.get("/blockchain/status")
def status():
    return jsonify(bs.status(check_connection=request.args.get("check") == "1"))


@bp.post("/evidence/<eid>/blockchain")
def submit(eid):
    payload, code = bs.submit_hash(get_db(), eid)
    return jsonify(payload), code


@bp.get("/evidence/<eid>/chain-check")
def chain_check(eid):
    payload, code = bs.read_onchain(get_db(), eid)
    return jsonify(payload), code
