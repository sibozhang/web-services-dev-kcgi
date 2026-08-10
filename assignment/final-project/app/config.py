import os
from datetime import timedelta


def _cors_origins() -> list[str]:
    value = os.getenv("CORS_ORIGINS", "https://localhost:2027")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://mlb:mlb@db:5432/mlb")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY", "dev-jwt-only-change-me-at-least-32-bytes"
    )
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "mlb_access_token"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = True
    JWT_CSRF_CHECK_FORM = True
    JWT_ACCESS_CSRF_FIELD_NAME = "csrf_token"
    JWT_COOKIE_SAMESITE = os.getenv("JWT_COOKIE_SAMESITE", "None")
    JWT_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "None")
    PREFERRED_URL_SCHEME = "https"
    FORCE_HTTPS = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    MLB_SEASON = int(os.getenv("MLB_SEASON", "2026"))
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Tokyo")
    MLB_BASE_URL = os.getenv("MLB_BASE_URL", "https://statsapi.mlb.com/api/v1")
    MLB_CONNECT_TIMEOUT = float(os.getenv("MLB_CONNECT_TIMEOUT", "3.05"))
    MLB_READ_TIMEOUT = float(os.getenv("MLB_READ_TIMEOUT", "15"))
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_LOGIN_REDIRECT_URI = os.getenv("GOOGLE_LOGIN_REDIRECT_URI", "")
    GOOGLE_CALENDAR_REDIRECT_URI = os.getenv("GOOGLE_CALENDAR_REDIRECT_URI", "")
    TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    BASE_URL = os.getenv("BASE_URL", "https://localhost:2028")
    CLIENT_URL = os.getenv("CLIENT_URL", "https://localhost:2027")
    CORS_ORIGINS = _cors_origins()


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite+pysqlite:///:memory:"
    JWT_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    FORCE_HTTPS = False
    JWT_SECRET_KEY = "test-jwt-key-with-more-than-thirty-two-bytes"
    SERVER_NAME = "localhost:2027"
