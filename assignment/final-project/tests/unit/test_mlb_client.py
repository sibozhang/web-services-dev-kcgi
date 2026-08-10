import json

import pytest
import requests

from app.services.mlb_client import MLBClient, MLBClientError


class FakeHeaders(dict):
    def update(self, values):
        super().update(values)


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        raise json.JSONDecodeError("bad", "", 0)


class FakeSession:
    def __init__(self):
        self.headers = FakeHeaders()
        self.mounted = {}

    def mount(self, prefix, adapter):
        self.mounted[prefix] = adapter

    def get(self, *_args, **_kwargs):
        return FakeResponse()


class RecordingSession(FakeSession):
    def get(self, url, **_kwargs):
        self.url = url
        response = FakeResponse()
        response.json = lambda: {}
        return response


def test_retry_configuration():
    client = MLBClient(retries=3)
    retry = client.session.get_adapter("https://").max_retries
    assert retry.total == 3
    assert set(MLBClient.RETRY_STATUSES).issubset(set(retry.status_forcelist))
    assert retry.backoff_factor == 0.5


def test_invalid_json_is_wrapped():
    client = MLBClient(session=FakeSession())
    with pytest.raises(MLBClientError):
        client.get("teams")


def test_live_feed_uses_v1_1_endpoint():
    session = RecordingSession()
    client = MLBClient(
        base_url="https://statsapi.mlb.com/api/v1",
        session=session,
    )

    assert client.live_feed(123456) == {}
    assert session.url == "https://statsapi.mlb.com/api/v1.1/game/123456/feed/live"
