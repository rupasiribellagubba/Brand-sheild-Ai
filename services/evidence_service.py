"""Evidence Vault: canonical JSON snapshots + SHA-256 integrity checks (works fully offline)."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from services import monitor_service
from services.common import log_activity, now_iso

CANDIDATE_FIELDS = ["id", "kind", "name", "username", "platform", "url", "description",
                    "developer", "app_id", "source", "status", "is_sample"]


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_evidence_id():
    return f"EV-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def create_evidence(db, cid):
    cand = monitor_service.get_candidate(db, cid)
    if cand is None:
        raise LookupError("Candidate not found")
    snapshot = {
        "candidate": {k: cand[k] for k in CANDIDATE_FIELDS},
        "assessment": {"id": cand["assessment_id"], "score": cand["score"], "level": cand["level"],
                       "indicators": cand["indicators"], "notes": cand["notes"]},
        "captured_at": now_iso(),
        "disclaimer": "Similarity-based risk signals; not confirmed fraud.",
    }
    text = canonical(snapshot)
    eid, digest = new_evidence_id(), sha256_hex(text)
    db.execute("INSERT INTO evidence (evidence_id, candidate_id, snapshot_json, sha256, created_at) VALUES (?,?,?,?,?)",
               (eid, cid, text, digest, now_iso()))
    log_activity(db, f"Evidence {eid} saved for '{cand['name']}'")
    db.commit()
    return get_evidence(db, eid)


def verify_evidence(db, eid):
    row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (eid,)).fetchone()
    if row is None:
        raise LookupError("Evidence not found")
    try:
        recomputed = sha256_hex(canonical(json.loads(row["snapshot_json"])))
    except (ValueError, TypeError):
        recomputed = sha256_hex(row["snapshot_json"])
    result = "intact" if recomputed == row["sha256"] else "tampered"
    db.execute("INSERT INTO verifications (evidence_id, result, recomputed_hash, verified_at) VALUES (?,?,?,?)",
               (eid, result, recomputed, now_iso()))
    log_activity(db, f"Evidence {eid} verified locally: {result}")
    db.commit()
    return {"evidence_id": eid, "result": result, "stored_hash": row["sha256"],
            "recomputed_hash": recomputed, "scope": "local SHA-256 check (not blockchain)"}


def _decorate(db, row):
    d = dict(row)
    d["snapshot"] = json.loads(d["snapshot_json"]) if _is_json(d["snapshot_json"]) else None
    v = db.execute("SELECT result, verified_at FROM verifications WHERE evidence_id = ? ORDER BY id DESC LIMIT 1",
                   (d["evidence_id"],)).fetchone()
    d["last_verification"] = dict(v) if v else None
    t = db.execute("SELECT tx_hash, status, error, contract_address, created_at FROM blockchain_tx "
                   "WHERE evidence_id = ? ORDER BY id DESC LIMIT 1", (d["evidence_id"],)).fetchone()
    d["blockchain"] = dict(t) if t else None
    d["candidate_name"] = (d["snapshot"] or {}).get("candidate", {}).get("name", "")
    return d


def _is_json(text):
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def get_evidence(db, eid):
    row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (eid,)).fetchone()
    return _decorate(db, row) if row else None


def list_evidence(db, candidate_id=None):
    sql, params = "SELECT * FROM evidence", []
    if candidate_id:
        sql += " WHERE candidate_id = ?"; params.append(candidate_id)
    return [_decorate(db, r) for r in db.execute(sql + " ORDER BY created_at DESC, rowid DESC", params)]


def verification_history(db, eid):
    return [dict(r) for r in db.execute(
        "SELECT result, recomputed_hash, verified_at FROM verifications WHERE evidence_id = ? ORDER BY id DESC", (eid,))]
