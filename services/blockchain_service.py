"""Optional Web3.py integration. Never fabricates tx hashes or addresses."""
import os

from services.common import log_activity, now_iso

ABI = [
    {"type": "function", "name": "recordEvidence", "stateMutability": "nonpayable",
     "inputs": [{"name": "evidenceId", "type": "string"}, {"name": "evidenceHash", "type": "bytes32"}], "outputs": []},
    {"type": "function", "name": "getEvidence", "stateMutability": "view",
     "inputs": [{"name": "evidenceId", "type": "string"}],
     "outputs": [{"name": "evidenceHash", "type": "bytes32"}, {"name": "timestamp", "type": "uint256"},
                 {"name": "recorder", "type": "address"}, {"name": "exists", "type": "bool"}]},
    {"type": "function", "name": "owner", "stateMutability": "view", "inputs": [],
     "outputs": [{"name": "", "type": "address"}]},
]


def _cfg():
    return {"rpc": os.getenv("WEB3_RPC_URL", "").strip(), "contract": os.getenv("CONTRACT_ADDRESS", "").strip(),
            "key": os.getenv("WALLET_PRIVATE_KEY", "").strip(), "chain": os.getenv("CHAIN_NAME", "test network")}


def web3_installed():
    try:
        import web3  # noqa: F401
        return True
    except ImportError:
        return False


def status(check_connection=False):
    c = _cfg()
    missing = [n for n, k in (("WEB3_RPC_URL", "rpc"), ("CONTRACT_ADDRESS", "contract"), ("WALLET_PRIVATE_KEY", "key")) if not c[k]]
    installed = web3_installed()
    out = {"configured": not missing and installed, "web3_installed": installed, "missing": missing,
           "chain": c["chain"], "contract_address": c["contract"] or None, "connected": None, "error": None,
           "label": "Blockchain Not Configured"}
    if missing or not installed:
        if not installed:
            out["error"] = "web3 package is not installed (pip install web3)."
        return out
    out["label"] = "Configured"
    if check_connection:
        try:
            w3 = _w3(c)
            out["connected"] = bool(w3.is_connected())
            if not out["connected"]:
                out["label"], out["error"] = "RPC Unreachable", "Could not connect to RPC endpoint."
        except Exception as exc:
            out.update(connected=False, label="RPC Unreachable", error=_safe(exc, c))
    return out


def _w3(c):
    from web3 import Web3
    return Web3(Web3.HTTPProvider(c["rpc"], request_kwargs={"timeout": 15}))


def _safe(exc, c):
    msg = f"{type(exc).__name__}: {exc}"
    return msg.replace(c["key"], "***") if c["key"] else msg


def _record_tx(db, eid, tx_hash, st, error, contract):
    db.execute("INSERT INTO blockchain_tx (evidence_id, tx_hash, status, error, contract_address, created_at) VALUES (?,?,?,?,?,?)",
               (eid, tx_hash, st, error, contract, now_iso()))
    db.commit()


def submit_hash(db, eid):
    """Returns (payload, http_status)."""
    row = db.execute("SELECT sha256 FROM evidence WHERE evidence_id = ?", (eid,)).fetchone()
    if row is None:
        raise LookupError("Evidence not found")
    st = status()
    if not st["configured"]:
        return {"ok": False, "label": st["label"], "error": "Blockchain Not Configured. " + (st["error"] or
                "Missing: " + ", ".join(st["missing"]))}, 503
    c = _cfg()
    try:
        from web3 import Web3
        w3 = _w3(c)
        if not w3.is_connected():
            raise ConnectionError("RPC endpoint unreachable")
        acct = w3.eth.account.from_key(c["key"])
        contract = w3.eth.contract(address=Web3.to_checksum_address(c["contract"]), abi=ABI)
        tx = contract.functions.recordEvidence(eid, bytes.fromhex(row["sha256"])).build_transaction({
            "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address), "chainId": w3.eth.chain_id})
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        tx_hash = w3.eth.send_raw_transaction(raw).hex()
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
        final = "confirmed" if receipt["status"] == 1 else "failed"
        tx_hash = tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash
        _record_tx(db, eid, tx_hash, final, "" if final == "confirmed" else "Transaction reverted", c["contract"])
        log_activity(db, f"Evidence {eid} blockchain tx {final}"); db.commit()
        return {"ok": final == "confirmed", "tx_hash": tx_hash, "status": final, "explorer": explorer_url(tx_hash)}, 200 if final == "confirmed" else 502
    except Exception as exc:
        err = _safe(exc, c)
        _record_tx(db, eid, "", "failed", err, c["contract"])
        return {"ok": False, "status": "failed", "error": err}, 502


def explorer_url(tx_hash):
    base = os.getenv("EXPLORER_TX_URL", "").strip()
    return base + tx_hash if base and tx_hash else None


def read_onchain(db, eid):
    """Compare locally stored hash with the hash read from the contract."""
    row = db.execute("SELECT sha256 FROM evidence WHERE evidence_id = ?", (eid,)).fetchone()
    if row is None:
        raise LookupError("Evidence not found")
    st = status()
    if not st["configured"]:
        return {"ok": False, "label": st["label"], "error": "Blockchain Not Configured."}, 503
    c = _cfg()
    try:
        from web3 import Web3
        contract = _w3(c).eth.contract(address=Web3.to_checksum_address(c["contract"]), abi=ABI)
        h, ts, recorder, exists = contract.functions.getEvidence(eid).call()
        if not exists:
            return {"ok": True, "recorded": False, "message": "Not recorded on-chain."}, 200
        onchain = h.hex().removeprefix("0x")
        return {"ok": True, "recorded": True, "onchain_hash": onchain, "timestamp": ts, "recorder": recorder,
                "matches_local": onchain == row["sha256"], "scope": "blockchain check"}, 200
    except Exception as exc:
        return {"ok": False, "error": _safe(exc, c)}, 502
