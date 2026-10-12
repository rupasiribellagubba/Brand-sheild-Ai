from flask import Blueprint

from routes._candidate_api import register

bp = Blueprint("social", __name__, url_prefix="/api/social")
register(bp, "social")
