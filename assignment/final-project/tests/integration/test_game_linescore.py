import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.extensions import db
from app.models import AIAnalysis, Game, GameSnapshot, Team


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_live_game_shows_nine_innings_when_only_six_are_available(app, client):
    with app.app_context():
        away = Team(
            mlb_team_id=301,
            name="Away Club",
            abbreviation="AWY",
            league="AL",
            division="AL East",
        )
        home = Team(
            mlb_team_id=302,
            name="Home Club",
            abbreviation="HME",
            league="NL",
            division="NL East",
        )
        db.session.add_all([away, home])
        db.session.flush()
        game = Game(
            game_pk=990001,
            season=2026,
            official_date=date(2026, 7, 20),
            start_time_utc=datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc),
            start_time_jst=datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=2,
            away_score=3,
            normalized_status="LIVE",
            current_inning=6,
            inning_half="Bottom",
        )
        db.session.add(game)
        db.session.flush()
        innings = [
            {
                "num": number,
                "away": {"runs": 1 if number in {1, 3, 5} else 0},
                "home": {"runs": 1 if number in {2, 4} else 0},
            }
            for number in range(1, 7)
        ]
        db.session.add(
            GameSnapshot(
                game_pk=game.game_pk,
                snapshot_type="LIVE",
                source_hash="a" * 64,
                payload={
                    "linescore": {
                        "innings": innings,
                        "teams": {
                            "away": {"runs": 3, "hits": 7, "errors": 0},
                            "home": {"runs": 2, "hits": 5, "errors": 1},
                        },
                    }
                },
            )
        )
        boxscore_payload = json.loads((FIXTURES / "boxscore.json").read_text())
        away_boxscore = boxscore_payload["teams"]["away"]
        away_boxscore["pitchers"] = [990099]
        away_boxscore["players"]["ID990099"] = {
            "person": {"id": 990099, "fullName": "Live Pitcher"},
            "position": {"abbreviation": "P"},
            "stats": {
                "pitching": {
                    "inningsPitched": "5.2",
                    "hits": 5,
                    "runs": 2,
                    "earnedRuns": 2,
                    "baseOnBalls": 1,
                    "strikeOuts": 6,
                    "homeRuns": 1,
                }
            },
            "seasonStats": {"pitching": {"era": "3.21"}},
        }
        away_boxscore["bullpen"] = [990100]
        away_boxscore["players"]["ID990100"] = {
            "person": {"id": 990100, "fullName": "Bullpen Option"},
            "position": {"abbreviation": "P"},
            "stats": {"pitching": {}},
            "seasonStats": {
                "pitching": {
                    "gamesPlayed": 35,
                    "inningsPitched": "38.0",
                    "era": "2.84",
                    "whip": "1.08",
                    "saves": 12,
                    "holds": 4,
                    "blownSaves": 2,
                    "strikeOuts": 43,
                    "baseOnBalls": 11,
                }
            },
            "gameStatus": {"isOnBench": True},
        }
        db.session.add(
            GameSnapshot(
                game_pk=game.game_pk,
                snapshot_type="BOX_SCORE",
                source_hash="b" * 64,
                payload=boxscore_payload,
            )
        )
        db.session.add_all(
            [
                AIAnalysis(
                    game_pk=game.game_pk,
                    analysis_type="PRE_GAME",
                    source_hash="c" * 64,
                    model_name="test-model",
                    prompt_version="pre-game-v1",
                    content={"overview": "过时的赛前分析"},
                    created_at=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
                ),
                AIAnalysis(
                    game_pk=game.game_pk,
                    analysis_type="LIVE",
                    source_hash="d" * 64,
                    model_name="test-model",
                    prompt_version="live-v1",
                    content={"current_situation": "较早的进行中分析"},
                    created_at=datetime(2026, 7, 20, 1, 5, tzinfo=timezone.utc),
                ),
                AIAnalysis(
                    game_pk=game.game_pk,
                    analysis_type="LIVE",
                    source_hash="e" * 64,
                    model_name="test-model",
                    prompt_version="live-v6",
                    content={"current_situation": "最新的进行中分析"},
                    created_at=datetime(2026, 7, 20, 1, 10, tzinfo=timezone.utc),
                ),
            ]
        )
        db.session.commit()

    client.post(
        "/api/auth/register",
        json={"email": "linescore@example.com", "password": "long-password"},
    )
    response = client.get("/api/games/990001")
    linescore = response.get_json()["data"]["linescore"]

    assert response.status_code == 200
    assert len(linescore["innings"]) == 6
    assert linescore["innings"][5]["number"] == 6
    assert linescore["totals"]["away"]["runs"] == 3
    assert "offense" not in linescore
    assert "defense" not in linescore
    analyses = response.get_json()["data"]["analyses"]
    assert len(analyses) == 1
    assert analyses[0]["analysis_type"] == "LIVE"
    assert analyses[0]["content"] == {"current_situation": "最新的进行中分析"}
    assert analyses[0]["created_at"].startswith("2026-07-20T01:10:00")

    status_response = client.get("/api/games/990001/status")
    status_data = status_response.get_json()["data"]
    assert status_response.status_code == 200
    assert status_data["boxscore"]["away"]["batters"]
    assert status_data["boxscore"]["away"]["pitchers"]
    assert status_data["boxscore"]["away"]["bullpen"]
    assert status_data["boxscore"]["away"]["pitchers"][0]["player_id"] == 990099
    assert status_data["active_rosters"]["away"]["count"] == 0
