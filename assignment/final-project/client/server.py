import json
import os
import ssl
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


STATIC_ROOT = Path("/srv")
PORT = 2027


class SpaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_ROOT, **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._send_bytes(
                json.dumps({"status": "ok"}).encode(),
                "application/json; charset=utf-8",
            )
            return
        if path == "/runtime-config.js":
            api_base_url = os.getenv("API_BASE_URL", "https://localhost:2028")
            script = f"window.MLB_API_BASE_URL = {json.dumps(api_base_url)};\n"
            self._send_bytes(
                script.encode(),
                "application/javascript; charset=utf-8",
            )
            return

        requested = STATIC_ROOT / path.lstrip("/")
        if path != "/" and not requested.is_file():
            self.path = "/index.html"
        super().do_GET()

    def _send_bytes(self, body: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


server = ThreadingHTTPServer(("0.0.0.0", PORT), SpaHandler)
if os.getenv("TLS_MODE", "direct") == "direct":
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(
        os.getenv("TLS_CERT_FILE", "/tmp/mlb-dugout.crt"),
        os.getenv("TLS_KEY_FILE", "/tmp/mlb-dugout.key"),
    )
    server.socket = tls.wrap_socket(server.socket, server_side=True)
server.serve_forever()
