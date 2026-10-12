from flask import Blueprint

from routes._candidate_api import register

bp = Blueprint("app_monitor", __name__, url_prefix="/api/apps")
register(bp, "app")
