from datetime import datetime, timezone


class ValidationError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or []


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_activity(db, message):
    db.execute("INSERT INTO activity (message, created_at) VALUES (?, ?)", (message, now_iso()))
