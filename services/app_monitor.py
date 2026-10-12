"""App-store monitoring: CSV/manual records only (no live store scraping)."""
from services import monitor_service as ms

KIND = "app"


def add(db, data):
    return ms.add_candidate(db, KIND, data)


def import_csv(db, text):
    return ms.import_csv(db, KIND, text)


def search(db, **filters):
    return ms.list_candidates(db, kind=KIND, **filters)
