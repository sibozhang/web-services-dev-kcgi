from pathlib import Path

from cryptography import x509

from app import create_app
from app.config import TestConfig
from app.extensions import db
from scripts.generate_dev_certificate import generate


ROOT = Path(__file__).parents[2]


class HttpsConfig(TestConfig):
    FORCE_HTTPS = True
    JWT_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True


def test_http_redirects_to_https():
    app = create_app(HttpsConfig)
    with app.app_context():
        db.create_all()
        response = app.test_client().get(
            "/", base_url="http://localhost:2027", follow_redirects=False
        )
        assert response.status_code == 308
        assert response.location == "https://localhost:2027/"


def test_https_response_includes_hsts():
    app = create_app(HttpsConfig)
    with app.app_context():
        db.create_all()
        response = app.test_client().get(
            "/api/health", base_url="https://localhost:2027"
        )
        assert response.status_code == 200
        assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_generated_certificate_covers_localhost(tmp_path):
    cert_path = tmp_path / "localhost.crt"
    key_path = tmp_path / "localhost.key"
    generate(cert_path, key_path)

    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san = certificate.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    assert "localhost" in san.get_values_for_type(x509.DNSName)
    assert key_path.stat().st_mode & 0o777 == 0o600


def test_client_skips_local_certificate_when_azure_terminates_tls():
    server = (ROOT / "client" / "server.py").read_text()

    assert 'os.getenv("TLS_MODE", "direct") == "direct"' in server
    assert "server.socket = tls.wrap_socket" in server
