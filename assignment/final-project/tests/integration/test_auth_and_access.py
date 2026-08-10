from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models import Game, Team, User
from app.services.ai_service import AIRateLimitError


def _seed_game():
    away = Team(
        mlb_team_id=1,
        name="Away",
        abbreviation="AWY",
        league="AL",
        division="AL East",
    )
    home = Team(
        mlb_team_id=2,
        name="Home",
        abbreviation="HME",
        league="NL",
        division="NL East",
    )
    db.session.add_all([away, home])
    db.session.flush()
    game = Game(
        game_pk=100,
        season=2026,
        official_date=date(2026, 7, 21),
        start_time_utc=datetime.now(timezone.utc) + timedelta(days=1),
        start_time_jst=datetime.now(timezone.utc) + timedelta(days=1, hours=9),
        home_team_id=home.id,
        away_team_id=away.id,
        normalized_status="SCHEDULED",
    )
    db.session.add(game)
    db.session.commit()
    return game


def test_visitor_gets_json_401_from_protected_game_api(app, client):
    with app.app_context():
        _seed_game()
    response = client.get("/api/games/100")
    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_register_login_and_jwt_cookie(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "USER@Example.com ", "password": "long-password"},
    )
    assert response.status_code == 201
    assert response.is_json
    assert response.get_json()["data"]["user"]["email"] == "user@example.com"
    cookies = response.headers.getlist("Set-Cookie")
    assert any("mlb_access_token=" in cookie and "HttpOnly" in cookie for cookie in cookies)
    assert any("csrf_access_token=" in cookie for cookie in cookies)


def test_login_failure_does_not_reveal_account(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "long-password"},
    )
    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()["error"]["message"] == "邮箱或密码不正确。"


def test_authenticated_page_still_opens_when_ai_unconfigured(app, client):
    with app.app_context():
        _seed_game()
    client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "long-password"},
    )
    response = client.get("/api/games/100")
    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()["data"]
    assert payload["game"]["game_pk"] == 100
    assert payload["game"]["status"]["normalized"] == "SCHEDULED"
    assert payload["analyses"] == []


def test_pregame_analysis_endpoint_requires_both_probable_pitchers(app, client):
    with app.app_context():
        _seed_game()
    client.post(
        "/api/auth/register",
        json={"email": "pregame@example.com", "password": "long-password"},
    )
    csrf = client.get_cookie("csrf_access_token").value

    response = client.post(
        "/api/games/100/analyses",
        headers={"X-CSRF-TOKEN": csrf},
        json={},
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == {
        "code": "PROBABLE_PITCHERS_REQUIRED",
        "message": "双方预告先发投手公布后才能生成 AI 赛前展望。",
    }


def test_ai_rate_limit_returns_retry_metadata(app, client, monkeypatch):
    with app.app_context():
        game = _seed_game()
        game.normalized_status = "LIVE"
        db.session.commit()

    class RateLimitedAIService:
        def __init__(self, **_kwargs):
            pass

        def analyze_game(self, _game, _details, **_kwargs):
            raise AIRateLimitError(24)

    monkeypatch.setattr(
        "app.blueprints.api.routes.AIService", RateLimitedAIService
    )
    client.post(
        "/api/auth/register",
        json={"email": "rate-limit@example.com", "password": "long-password"},
    )
    csrf = client.get_cookie("csrf_access_token").value

    response = client.post(
        "/api/games/100/analyses",
        headers={"X-CSRF-TOKEN": csrf},
        json={},
    )

    assert response.status_code == 429
    assert response.get_json()["error"] == {
        "code": "AI_RATE_LIMITED",
        "message": "Gemini 免费配额暂时受限，请在 24 秒后重试。",
        "retry_after": 24,
    }


def test_session_endpoint_reports_current_user(client):
    client.post(
        "/api/auth/register",
        json={"email": "session@example.com", "password": "long-password"},
    )
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["authenticated"] is True
    assert data["user"]["email"] == "session@example.com"
    assert data["csrf_token"] == client.get_cookie("csrf_access_token").value


def test_protected_post_distinguishes_missing_csrf_from_logged_out(client):
    client.post(
        "/api/auth/register",
        json={"email": "csrf@example.com", "password": "long-password"},
    )

    response = client.post("/api/sync/games", json={})

    assert response.status_code == 401
    assert response.get_json()["error"] == {
        "code": "CSRF_VALIDATION_FAILED",
        "message": "安全验证信息缺失或已过期，请刷新页面后重试。",
    }


def test_manual_game_sync_requires_login(client):
    response = client.post("/api/sync/games", json={})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_authenticated_user_can_trigger_manual_game_sync(client, monkeypatch):
    calls = []

    class FakeSyncService:
        def __init__(self, _client):
            pass

        def sync_schedule(self, start, end):
            calls.append(("schedule", start, end))
            return 27

        def sync_live_games(self):
            calls.append(("live",))
            return 3

    monkeypatch.setattr(
        "app.blueprints.api.routes._today_jst", lambda: date(2026, 7, 21)
    )
    monkeypatch.setattr(
        "app.blueprints.api.routes.MLBSyncService", FakeSyncService
    )
    client.post(
        "/api/auth/register",
        json={"email": "sync@example.com", "password": "long-password"},
    )
    csrf = client.get_cookie("csrf_access_token").value

    response = client.post(
        "/api/sync/games",
        json={},
        headers={"X-CSRF-TOKEN": csrf},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["schedule_window"] == {
        "start": "2026-07-20",
        "end": "2026-07-21",
    }
    assert payload["data"]["games_synced"] == 27
    assert payload["data"]["live_games_synced"] == 3
    assert calls == [
        ("schedule", date(2026, 7, 20), date(2026, 7, 21)),
        ("live",),
    ]
