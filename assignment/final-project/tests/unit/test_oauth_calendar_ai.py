from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import requests
from cryptography.fernet import Fernet

from app.extensions import db
from app.models import (
    AIAnalysis,
    CalendarGameEvent,
    Game,
    GoogleCalendarToken,
    Player,
    PlayerPitchingStats,
    Team,
    User,
)
from app.services.ai_service import (
    AIRateLimitError,
    AIService,
    PregameAnalysisUnavailable,
)
from app.services.auth_service import validate_oauth_state
from app.services.google_calendar_service import GoogleCalendarService
from app.services.token_service import TokenCipher


def _entities():
    user = User(email="user@example.com")
    away = Team(mlb_team_id=10, name="Away", abbreviation="A", league="AL", division="AL East")
    home = Team(mlb_team_id=20, name="Home", abbreviation="H", league="NL", division="NL East")
    db.session.add_all([user, away, home])
    db.session.flush()
    game = Game(
        game_pk=200,
        season=2026,
        official_date=date(2026, 8, 1),
        start_time_utc=datetime.now(timezone.utc) + timedelta(days=5),
        start_time_jst=datetime.now(timezone.utc) + timedelta(days=5, hours=9),
        home_team_id=home.id,
        away_team_id=away.id,
        normalized_status="SCHEDULED",
    )
    db.session.add(game)
    db.session.commit()
    return user, game


def _publish_probables(game):
    away_pitcher = Player(mlb_player_id=301, full_name="Away Starter")
    home_pitcher = Player(mlb_player_id=302, full_name="Home Opener")
    db.session.add_all([away_pitcher, home_pitcher])
    db.session.flush()
    game.probable_away_pitcher_id = away_pitcher.id
    game.probable_home_pitcher_id = home_pitcher.id
    db.session.commit()
    return away_pitcher, home_pitcher


def test_oauth_state_validation():
    assert validate_oauth_state("same-value", "same-value")
    assert not validate_oauth_state("same-value", "other")
    assert not validate_oauth_state(None, "other")


def test_calendar_duplicate_short_circuits_api(app):
    with app.app_context():
        user, game = _entities()
        existing = CalendarGameEvent(
            user_id=user.id, game_pk=game.game_pk, google_event_id="existing"
        )
        db.session.add(existing)
        db.session.commit()
        service = GoogleCalendarService(
            "client",
            "secret",
            TokenCipher(Fernet.generate_key().decode()),
            "https://localhost:2027",
        )
        event, duplicate = service.add_game(user.id, game)
        assert duplicate is True
        assert event.google_event_id == "existing"


def test_ai_source_hash_cache(app):
    with app.app_context():
        _user, game = _entities()
        _publish_probables(game)
        service = AIService("", "")
        source = service.game_source(game)
        cached = AIAnalysis(
            game_pk=game.game_pk,
            analysis_type="PRE_GAME",
            source_hash=service.cache_hash(source),
            model_name="configured-by-env",
            prompt_version=service.PROMPT_VERSION,
            content={"overview": "cached"},
        )
        db.session.add(cached)
        db.session.commit()
        analysis, cache_hit = service.analyze_game(game)
        assert cache_hit is True
        assert analysis.content["overview"] == "cached"


def test_pregame_ai_requires_both_probable_pitchers(app):
    with app.app_context():
        _user, game = _entities()
        away_pitcher = Player(mlb_player_id=303, full_name="Away Starter")
        db.session.add(away_pitcher)
        db.session.flush()
        game.probable_away_pitcher_id = away_pitcher.id
        db.session.commit()

        service = AIService("test-api-key", "gemini-flash-latest")
        with pytest.raises(PregameAnalysisUnavailable):
            service.analyze_game(game)


def test_pregame_source_includes_pitcher_usage_and_recent_form(app):
    with app.app_context():
        _user, game = _entities()
        away_pitcher, home_pitcher = _publish_probables(game)
        db.session.add_all(
            [
                PlayerPitchingStats(
                    player_id=away_pitcher.id,
                    team_id=game.away_team_id,
                    season=game.season,
                    games_played=20,
                    games_started=20,
                    wins=8,
                    losses=4,
                    innings_outs=330,
                    strikeouts=105,
                    walks=25,
                    era=Decimal("3.18"),
                    whip=Decimal("1.09"),
                ),
                PlayerPitchingStats(
                    player_id=home_pitcher.id,
                    team_id=game.home_team_id,
                    season=game.season,
                    games_played=28,
                    games_started=2,
                    wins=2,
                    losses=1,
                    innings_outs=90,
                    strikeouts=24,
                    walks=10,
                    era=Decimal("4.20"),
                    whip=Decimal("1.30"),
                ),
            ]
        )
        for index, away_wins in enumerate((True, False, True)):
            db.session.add(
                Game(
                    game_pk=400 + index,
                    season=game.season,
                    official_date=game.official_date - timedelta(days=index + 1),
                    start_time_utc=game.start_time_utc - timedelta(days=index + 1),
                    start_time_jst=game.start_time_jst - timedelta(days=index + 1),
                    home_team_id=game.home_team_id,
                    away_team_id=game.away_team_id,
                    away_score=5 if away_wins else 2,
                    home_score=2 if away_wins else 4,
                    normalized_status="FINAL",
                )
            )
        db.session.commit()

        service = AIService("test-api-key", "gemini-flash-latest")
        source = service.game_source(game)
        context = source["pregame_context"]

        assert context["away_probable_pitcher"]["season_stats"]["era"] == "3.18"
        assert context["away_probable_pitcher"]["season_stats"]["usage_pattern"] == "regular_starter_usage"
        assert context["home_probable_pitcher"]["season_stats"]["usage_pattern"] == "mixed_relief_or_opener_usage"
        assert context["recent_10"]["away"] == {
            "games": 3,
            "wins": 2,
            "losses": 1,
            "ties": 0,
        }
        assert context["recent_10"]["home"]["wins"] == 1


def test_pregame_prompt_and_content_are_short_and_structured():
    instructions = AIService._instructions("PRE_GAME")
    content = AIService._normalize_content(
        "PRE_GAME",
        {
            "starter_matchup": " 先发比较。 ",
            "team_form": "近期状态。",
            "outlook": "条件式展望。",
            "data_limitations": "不应展示",
        },
    )

    assert AIService.prompt_version_for("PRE_GAME") == "pre-game-v2"
    assert "总计不超过6句" in instructions
    assert "假先发" in instructions
    assert "recent_10" in instructions
    assert content == {
        "starter_matchup": "先发比较。",
        "team_form": "近期状态。",
        "outlook": "条件式展望。",
    }


def test_japanese_prompt_versions_use_separate_cache_namespace():
    assert AIService.prompt_version_for("PRE_GAME", "ja") == "pre-game-v2-ja"
    assert AIService.prompt_version_for("PLAYER", "ja") == "player-v1-ja"
    assert "自然な日本語" in AIService._instructions("LIVE", "ja")
    assert "自然な日本語" in AIService._player_instructions("ja")


class _PlayerGeminiResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"season_review":"今季は安定した成績です。",'
                                    '"recent_form":"直近の内容も良好です。",'
                                    '"outlook":"今後もデータを注視します。"}'
                                )
                            }
                        ]
                    }
                }
            ]
        }


class _PlayerGeminiSession:
    def __init__(self):
        self.calls = []

    def mount(self, *_args, **_kwargs):
        return None

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _PlayerGeminiResponse()


def test_player_analysis_is_generated_on_demand_and_cached_by_language(app):
    with app.app_context():
        player = Player(mlb_player_id=777001, full_name="Test Player")
        db.session.add(player)
        db.session.commit()
        session = _PlayerGeminiSession()
        service = AIService("test-api-key", "gemini-flash-latest", session=session)
        source = {"season": 2026, "hitting": [{"avg": ".300"}], "recent_appearances": {}}

        analysis, cached = service.analyze_player(player, source, language="ja")
        cached_analysis, second_cached = service.analyze_player(player, source, language="ja")

        assert cached is False
        assert second_cached is True
        assert cached_analysis.id == analysis.id
        assert analysis.prompt_version == "player-v1-ja"
        assert analysis.content["season_review"] == "今季は安定した成績です。"
        assert len(session.calls) == 1
        assert "自然な日本語" in session.calls[0][1]["json"]["contents"][0]["parts"][0]["text"]


class _GeminiResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"summary":"客队以3比1取胜。",'
                                    '"turning_point":"客队在第六局取得领先。",'
                                    '"key_players":["Winner Pitcher"],'
                                    '"home_team_review":"主队得到1分。",'
                                    '"away_team_review":"客队得到3分。"}'
                                )
                            }
                        ]
                    }
                }
            ]
        }


class _GeminiSession:
    def __init__(self):
        self.calls = []

    def mount(self, *_args, **_kwargs):
        return None

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _GeminiResponse()


class _RateLimitedResponse:
    status_code = 429

    def raise_for_status(self):
        raise requests.HTTPError("quota", response=self)

    def json(self):
        return {
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "24.2s",
                    }
                ]
            }
        }


class _RateLimitedSession:
    def mount(self, *_args, **_kwargs):
        return None

    def post(self, *_args, **_kwargs):
        return _RateLimitedResponse()


def test_ai_rate_limit_uses_retry_delay_without_generic_error(app):
    with app.app_context():
        _user, game = _entities()
        _publish_probables(game)
        service = AIService(
            "test-api-key",
            "gemini-flash-latest",
            session=_RateLimitedSession(),
        )

        with pytest.raises(AIRateLimitError) as caught:
            service.analyze_game(game)

        assert caught.value.retry_after == 25
        assert "25 秒后重试" in str(caught.value)


def test_ai_rate_limit_falls_back_to_latest_analysis(app):
    with app.app_context():
        _user, game = _entities()
        _publish_probables(game)
        previous = AIAnalysis(
            game_pk=game.game_pk,
            analysis_type="PRE_GAME",
            source_hash="old-source",
            model_name="gemini-flash-latest",
            prompt_version="pre-game-v1",
            content={"overview": "最近一次可用分析"},
        )
        db.session.add(previous)
        db.session.commit()
        service = AIService(
            "test-api-key",
            "gemini-flash-latest",
            session=_RateLimitedSession(),
        )

        analysis, cached = service.analyze_game(game)

        assert cached is True
        assert analysis.id == previous.id


class _CalendarResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"id": "google-event-id"}


class _CalendarSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _CalendarResponse()


def test_calendar_event_links_to_client(app):
    with app.app_context():
        user, game = _entities()
        key = Fernet.generate_key().decode()
        cipher = TokenCipher(key)
        token = GoogleCalendarToken(
            user_id=user.id,
            encrypted_access_token=cipher.encrypt("access-token"),
            encrypted_refresh_token=cipher.encrypt("refresh-token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes="https://www.googleapis.com/auth/calendar.events",
        )
        db.session.add(token)
        db.session.commit()
        session = _CalendarSession()
        service = GoogleCalendarService(
            "client",
            "secret",
            cipher,
            "https://localhost:2027",
            session=session,
        )

        event, duplicate = service.add_game(user.id, game)

        assert duplicate is False
        assert event.google_event_id == "google-event-id"
        assert len(session.calls) == 1
        url, request = session.calls[0]
        assert url.endswith("/calendars/primary/events")
        assert request["headers"]["Authorization"] == "Bearer access-token"
        assert (
            f"https://localhost:2027/games/{game.game_pk}"
            in request["json"]["description"]
        )
        assert request["json"]["start"]["timeZone"] == "Asia/Tokyo"
        assert request["json"]["end"]["timeZone"] == "Asia/Tokyo"


def test_ai_post_game_uses_header_and_structured_data(app):
    with app.app_context():
        _user, game = _entities()
        winner = Player(mlb_player_id=101, full_name="Winner Pitcher")
        loser = Player(mlb_player_id=102, full_name="Loser Pitcher")
        db.session.add_all([winner, loser])
        db.session.flush()
        game.normalized_status = "FINAL"
        game.away_score = 3
        game.home_score = 1
        game.winning_pitcher_id = winner.id
        game.losing_pitcher_id = loser.id
        db.session.commit()

        game_details = {
            "linescore": {
                "innings": [
                    {"number": 6, "away": {"runs": 2}, "home": {"runs": 0}}
                ]
            },
            "boxscore": {
                "away": {
                    "batters": [
                        {
                            "name": "Away Batter",
                            "hits": 2,
                            "home_runs": 1,
                            "rbi": 2,
                        }
                    ],
                    "pitchers": [
                        {
                            "name": "Winner Pitcher",
                            "role": "starter",
                            "innings": "6.0",
                        }
                    ],
                }
            },
        }
        session = _GeminiSession()
        service = AIService(
            "test-api-key",
            "gemini-flash-latest",
            session=session,
        )

        analysis, cache_hit = service.analyze_game(game, game_details)
        cached_analysis, second_cache_hit = service.analyze_game(game, game_details)

        assert cache_hit is False
        assert second_cache_hit is True
        assert cached_analysis.id == analysis.id
        assert analysis.analysis_type == "POST_GAME"
        assert analysis.content["summary"] == "客队以3比1取胜。"
        assert analysis.prompt_version == "post-game-v6"
        assert len(session.calls) == 1

        url, request = session.calls[0]
        assert url.endswith(
            "/v1beta/models/gemini-flash-latest:generateContent"
        )
        assert request["headers"]["X-goog-api-key"] == "test-api-key"
        assert "params" not in request
        prompt = request["json"]["contents"][0]["parts"][0]["text"]
        assert "Winner Pitcher" in prompt
        assert "Away Batter" in prompt
        assert '"home_runs": 1' in prompt
        assert '"role": "starter"' in prompt
        assert "只能使用提供的数据" in prompt
        generation_config = request["json"]["generationConfig"]
        assert generation_config["maxOutputTokens"] == 2048
        assert generation_config["thinkingConfig"]["thinkingLevel"] == "minimal"


def test_live_ai_prompt_is_compact_and_invalidates_old_prompt_cache(app):
    with app.app_context():
        _user, game = _entities()
        game.normalized_status = "LIVE"
        game.away_score = 5
        game.home_score = 8
        game.current_inning = 7
        game.inning_half = "Bottom"
        db.session.commit()
        service = AIService("test-api-key", "gemini-flash-latest")
        source = service.game_source(game, {"linescore": {}, "boxscore": {}})

        assert service.prompt_version_for("LIVE") == "live-v6"
        assert service.cache_hash(source, "LIVE") != service.source_hash(
            {
                "model_name": service.model_name,
                "prompt_version": "post-game-v6",
                "source": source,
            }
        )
        instructions = service._instructions("LIVE")
        assert "turning_points（1至3项字符串数组" in instructions
        assert "key_players（3至5项字符串数组" in instructions
        assert "bullpen_outlook（字符串，3至5句" in instructions
        assert "不要把失误、安打或保送写成失分的确定原因" in instructions
        assert "不要解释胜败投尚未产生" in instructions
        assert "不能出现当前局数、当前比分" in instructions
        assert "不得擅自写成“受制于投手群”" in instructions
        assert "不能写“可用”“可供选择”" in instructions
        assert "哪一队走势更有利" in instructions
        assert "不要返回data_limitations" in instructions


def test_live_ai_content_normalization_removes_extra_fields():
    content = AIService._normalize_content(
        "LIVE",
        {
            "turning_points": ["第1局主队建立领先。"] * 6,
            "key_players": "打者A贡献2分打点。",
            "bullpen_outlook": "主队在后半局面更有利，但走势取决于牛棚表现。",
            "data_limitations": "胜败投尚未产生。",
            "unexpected": {"nested": "value"},
        },
    )

    assert len(content["turning_points"]) == 3
    assert content["key_players"] == ["打者A贡献2分打点。"]
    assert "走势取决于牛棚表现" in content["bullpen_outlook"]
    assert "data_limitations" not in content
    assert "unexpected" not in content
