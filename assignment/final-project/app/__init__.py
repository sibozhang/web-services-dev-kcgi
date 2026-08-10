import logging
from pathlib import Path

from flask import Flask, redirect, request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import db, jwt, migrate, oauth
from app.models import User


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object or Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    oauth.init_app(app)
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": app.config["CORS_ORIGINS"],
                "allow_headers": ["Accept", "Content-Type", "X-CSRF-TOKEN"],
                "methods": ["GET", "POST", "OPTIONS"],
            }
        },
        supports_credentials=True,
    )

    if app.config.get("GOOGLE_CLIENT_ID"):
        oauth.register(
            name="google",
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            client_kwargs={"scope": "openid email profile"},
        )

    from app.blueprints.api.routes import bp as api_bp

    app.register_blueprint(api_bp)

    @app.before_request
    def enforce_https():
        if app.config.get("FORCE_HTTPS") and not request.is_secure:
            secure_url = request.url.replace(f"{request.scheme}://", "https://", 1)
            return redirect(secure_url, code=308)

    @app.after_request
    def add_https_headers(response):
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    from app.commands.sync_commands import register_commands

    register_commands(app)

    @jwt.user_lookup_loader
    def user_lookup(_header, jwt_data):
        try:
            return db.session.get(User, int(jwt_data["sub"]))
        except (TypeError, ValueError):
            return None

    @app.errorhandler(404)
    def not_found(_error):
        return {
            "error": {"code": "NOT_FOUND", "message": "请求的 API 资源不存在。"}
        }, 404

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务器暂时无法处理该请求。",
            }
        }, 500

    return app
