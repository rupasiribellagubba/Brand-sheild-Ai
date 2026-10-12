CREATE TABLE IF NOT EXISTS brand_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    website TEXT DEFAULT '',
    social_handles TEXT DEFAULT '',
    app_name TEXT DEFAULT '',
    app_id TEXT DEFAULT '',
    developer TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('social','app')),
    name TEXT NOT NULL,
    username TEXT DEFAULT '',
    platform TEXT DEFAULT '',
    url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    developer TEXT DEFAULT '',
    app_id TEXT DEFAULT '',
    source TEXT DEFAULT 'Manual entry',
    status TEXT NOT NULL DEFAULT 'New'
        CHECK (status IN ('New','Under Review','Confirmed Suspicious','False Positive')),
    is_sample INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    level TEXT NOT NULL,
    indicators TEXT NOT NULL,
    notes TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    summary_source TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    result TEXT NOT NULL CHECK (result IN ('intact','tampered')),
    recomputed_hash TEXT NOT NULL,
    verified_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blockchain_tx (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    tx_hash TEXT DEFAULT '',
    status TEXT NOT NULL,
    error TEXT DEFAULT '',
    contract_address TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cand_kind ON candidates(kind);
CREATE INDEX IF NOT EXISTS idx_assess_cand ON assessments(candidate_id);
