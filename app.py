import os

from flask import Flask, jsonify, request

from config import Config
from database.db import close_db, init_db
from services.common import ValidationError


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(close_db)
    init_db(app)  # database is created automatically on startup

    from routes import (app_monitor_routes, blockchain_routes, brand_routes, candidate_routes,
                        dashboard_routes, evidence_routes, social_routes)
    for mod in (dashboard_routes, brand_routes, social_routes, app_monitor_routes,
                candidate_routes, evidence_routes, blockchain_routes):
        app.register_blueprint(mod.bp)

    @app.errorhandler(ValidationError)
    def _validation(e):
        return jsonify({"error": e.message, "details": e.details}), 400

    @app.errorhandler(LookupError)
    def _lookup(e):
        return jsonify({"error": str(e)}), 404

    @app.errorhandler(404)
    def _404(_e):
        return (jsonify({"error": "Not found"}), 404) if request.path.startswith("/api") else ("Page not found", 404)

    @app.errorhandler(413)
    def _413(_e):
        return jsonify({"error": "File too large (max 1 MB)."}), 413

    @app.errorhandler(500)
    def _500(_e):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
