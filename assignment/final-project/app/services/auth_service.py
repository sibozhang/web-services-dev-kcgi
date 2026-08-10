import secrets
from urllib.parse import urlparse

from flask import request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    set_access_cookies,
    verify_jwt_in_request,
)

from app.extensions import db
from app.models import User


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def validate_password(password: str) -> str | None:
    if len(password) < 10:
        return "密码至少需要 10 个字符。"
    if len(password) > 128:
        return "密码不能超过 128 个字符。"
    return None


def issue_login_cookie(response, user: User):
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    set_access_cookies(response, token)
    return response


def current_user() -> User | None:
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
    except Exception:
        return None
    if not identity:
        return None
    return db.session.get(User, int(identity))


def safe_next_url(value: str | None, fallback: str = "/") -> str:
    if not value:
        return fallback
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return fallback
    return value


def new_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def validate_oauth_state(expected: str | None, received: str | None) -> bool:
    return bool(expected and received and secrets.compare_digest(expected, received))

