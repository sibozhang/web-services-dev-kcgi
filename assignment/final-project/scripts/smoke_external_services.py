#!/usr/bin/env python3
"""手动外部服务 smoke test；不会被默认 pytest 执行。"""

import argparse
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.mlb_client import MLBClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--google", action="store_true", help="检查 Google OIDC discovery")
    parser.add_argument("--gemini", action="store_true", help="发起一次最小 Gemini 请求（可能计费）")
    args = parser.parse_args()

    teams = MLBClient().teams().get("teams", [])
    print(f"MLB: OK ({len(teams)} teams)")

    if args.google:
        response = requests.get(
            "https://accounts.google.com/.well-known/openid-configuration", timeout=(3.05, 10)
        )
        response.raise_for_status()
        print(f"Google OIDC: OK ({response.json().get('issuer')})")

    if args.gemini:
        key = os.environ.get("GEMINI_API_KEY")
        model = os.environ.get("GEMINI_MODEL")
        if not key or not model:
            raise SystemExit("GEMINI_API_KEY/GEMINI_MODEL are required")
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": "Return JSON: {\"status\":\"ok\"}"}]}]},
            timeout=(3.05, 20),
        )
        response.raise_for_status()
        print("Gemini: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

