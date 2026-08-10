from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import (
    CalendarGameEvent,
    Game,
    GameSnapshot,
    GoogleCalendarToken,
    Player,
    PlayerHittingStats,
    PlayerPitchingStats,
    Roster,
    Standing,
    Team,
    User,
)


def _seed_final_game():
    away = Team(
        mlb_team_id=145,
        name="Chicago White Sox",
        abbreviation="CWS",
        league="AL",
        division="AL Central",
    )
    home = Team(
        mlb_team_id=141,
        name="Toronto Blue Jays",
        abbreviation="TOR",
        league="AL",
        division="AL East",
    )
    winner = Player(mlb_player_id=680732, full_name="Sean Burke")
    loser = Player(mlb_player_id=702056, full_name="Trey Yesavage")
    save = Player(mlb_player_id=691799, full_name="Grant Taylor")
    db.session.add_all([away, home, winner, loser, save])
    db.session.flush()

    now = datetime.now(timezone.utc)
    game = Game(
        game_pk=822786,
        season=2026,
        game_type="R",
        official_date=now.date(),
        start_time_utc=now,
        start_time_jst=now,
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=0,
        away_score=3,
        normalized_status="FINAL",
        probable_away_pitcher_id=winner.id,
        probable_home_pitcher_id=loser.id,
        winning_pitcher_id=winner.id,
        losing_pitcher_id=loser.id,
        save_pitcher_id=save.id,
    )
    db.session.add(game)
    db.session.add(
        GameSnapshot(
            game_pk=game.game_pk,
            snapshot_type="BOX_SCORE",
            source_hash="b" * 64,
            payload={
                "teams": {
                    "away": {
                        "team": {"id": away.mlb_team_id, "name": away.name},
                        "batters": [673357],
                        "pitchers": [winner.mlb_player_id, save.mlb_player_id],
                        "players": {
                            "ID673357": {
                                "person": {
                                    "id": 673357,
                                    "fullName": "Luis Robert Jr.",
                                },
                                "position": {"abbreviation": "CF"},
                                "battingOrder": "100",
                                "stats": {
                                    "batting": {
                                        "gamesPlayed": 1,
                                        "atBats": 4,
                                        "runs": 1,
                                        "hits": 2,
                                        "rbi": 2,
                                        "baseOnBalls": 0,
                                        "strikeOuts": 1,
                                    }
                                },
                                "seasonStats": {
                                    "batting": {"avg": ".281", "ops": ".842"}
                                },
                            },
                            "ID680732": {
                                "person": {
                                    "id": winner.mlb_player_id,
                                    "fullName": winner.full_name,
                                },
                                "position": {"abbreviation": "P"},
                                "stats": {
                                    "pitching": {
                                        "note": "(W, 7-8)",
                                        "inningsPitched": "7.0",
                                        "hits": 3,
                                        "runs": 0,
                                        "earnedRuns": 0,
                                        "baseOnBalls": 1,
                                        "strikeOuts": 6,
                                        "homeRuns": 0,
                                    }
                                },
                                "seasonStats": {"pitching": {"era": "4.11"}},
                            },
                            "ID691799": {
                                "person": {
                                    "id": save.mlb_player_id,
                                    "fullName": save.full_name,
                                },
                                "position": {"abbreviation": "P"},
                                "stats": {
                                    "pitching": {
                                        "note": "(S, 8)",
                                        "inningsPitched": "1.0",
                                        "hits": 0,
                                        "runs": 0,
                                        "earnedRuns": 0,
                                        "baseOnBalls": 0,
                                        "strikeOuts": 2,
                                        "homeRuns": 0,
                                    }
                                },
                                "seasonStats": {"pitching": {"era": "2.18"}},
                            },
                        },
                        "teamStats": {
                            "batting": {
                                "atBats": 31,
                                "runs": 3,
                                "hits": 6,
                                "rbi": 3,
                                "baseOnBalls": 2,
                                "strikeOuts": 12,
                            },
                            "pitching": {
                                "inningsPitched": "9.0",
                                "hits": 4,
                                "runs": 0,
                                "earnedRuns": 0,
                                "baseOnBalls": 1,
                                "strikeOuts": 8,
                                "homeRuns": 0,
                            },
                        },
                    },
                    "home": {
                        "team": {"id": home.mlb_team_id, "name": home.name},
                        "batters": [666182],
                        "pitchers": [loser.mlb_player_id],
                        "players": {
                            "ID666182": {
                                "person": {
                                    "id": 666182,
                                    "fullName": "Bo Bichette",
                                },
                                "position": {"abbreviation": "SS"},
                                "battingOrder": "100",
                                "stats": {
                                    "batting": {
                                        "gamesPlayed": 1,
                                        "atBats": 4,
                                        "runs": 0,
                                        "hits": 1,
                                        "rbi": 0,
                                        "baseOnBalls": 0,
                                        "strikeOuts": 1,
                                    }
                                },
                                "seasonStats": {
                                    "batting": {"avg": ".302", "ops": ".801"}
                                },
                            },
                            "ID702056": {
                                "person": {
                                    "id": loser.mlb_player_id,
                                    "fullName": loser.full_name,
                                },
                                "position": {"abbreviation": "P"},
                                "stats": {
                                    "pitching": {
                                        "note": "(L, 3-5)",
                                        "inningsPitched": "5.2",
                                        "hits": 5,
                                        "runs": 3,
                                        "earnedRuns": 3,
                                        "baseOnBalls": 2,
                                        "strikeOuts": 7,
                                        "homeRuns": 1,
                                    }
                                },
                                "seasonStats": {"pitching": {"era": "4.37"}},
                            },
                        },
                        "teamStats": {
                            "batting": {
                                "atBats": 30,
                                "runs": 0,
                                "hits": 4,
                                "rbi": 0,
                                "baseOnBalls": 1,
                                "strikeOuts": 8,
                            },
                            "pitching": {
                                "inningsPitched": "9.0",
                                "hits": 6,
                                "runs": 3,
                                "earnedRuns": 3,
                                "baseOnBalls": 2,
                                "strikeOuts": 12,
                                "homeRuns": 1,
                            },
                        },
                    },
                }
            },
        )
    )
    db.session.add_all(
        [
            Standing(
                season=2026,
                team_id=away.id,
                wins=57,
                losses=42,
                division_rank=2,
            ),
            Standing(
                season=2026,
                team_id=home.id,
                wins=51,
                losses=48,
                division_rank=4,
            ),
            PlayerPitchingStats(
                player_id=winner.id,
                team_id=away.id,
                season=2026,
                wins=7,
                losses=8,
                era=Decimal("4.11"),
            ),
            PlayerPitchingStats(
                player_id=loser.id,
                team_id=home.id,
                season=2026,
                wins=3,
                losses=5,
                era=Decimal("4.37"),
            ),
            PlayerPitchingStats(
                player_id=save.id,
                team_id=away.id,
                season=2026,
                wins=2,
                losses=1,
                saves=8,
                era=Decimal("2.18"),
            ),
        ]
    )
    db.session.commit()


def test_games_api_returns_records_and_simplified_decisions(app, client):
    with app.app_context():
        _seed_final_game()

    response = client.get("/api/games")
    payload = response.get_json()
    game = payload["data"][0]

    assert response.status_code == 200
    assert game["away"]["standing"]["wins"] == 57
    assert game["away"]["standing"]["losses"] == 42
    assert game["home"]["standing"]["wins"] == 51
    assert game["home"]["standing"]["losses"] == 48
    assert [item["code"] for item in game["decisions"]] == ["W", "L", "S"]
    assert game["decisions"][0]["pitcher"]["full_name"] == "Sean Burke"
    assert game["decisions"][0]["season_stats"]["wins"] == 7
    assert game["decisions"][0]["season_stats"]["era"] == "4.11"
    assert game["decisions"][2]["season_stats"]["saves"] == 8
    assert game["away"]["probable_pitcher"]["season_stats"]["wins"] == 7
    assert game["away"]["probable_pitcher"]["season_stats"]["losses"] == 8
    assert game["away"]["probable_pitcher"]["season_stats"]["era"] == "4.11"
    assert "snapshot" not in game


def test_standings_api_omits_removed_team_stats_payload(app, client):
    with app.app_context():
        _seed_final_game()

    response = client.get("/api/standings?season=2026")
    rows = response.get_json()["data"]["divisions"]["AL Central"]

    assert response.status_code == 200
    assert rows[0]["team"]["abbreviation"] == "CWS"
    assert "season_stats" not in rows[0]


def test_team_roster_api_groups_active_players_and_simplifies_stats(app, client):
    with app.app_context():
        _seed_final_game()
        away = db.session.execute(
            db.select(Team).where(Team.mlb_team_id == 145)
        ).scalar_one()
        pitcher = db.session.execute(
            db.select(Player).where(Player.mlb_player_id == 680732)
        ).scalar_one()
        pitcher.pitch_hand = "Right"
        hitter = Player(
            mlb_player_id=700001,
            full_name="Roster Hitter",
            primary_position="CF",
            bat_side="Left",
            pitch_hand="Right",
        )
        db.session.add(hitter)
        db.session.flush()
        db.session.add_all(
            [
                Roster(
                    team_id=away.id,
                    player_id=pitcher.id,
                    season=2026,
                    jersey_number="18",
                    position="P",
                    roster_status="Active",
                ),
                Roster(
                    team_id=away.id,
                    player_id=hitter.id,
                    season=2026,
                    jersey_number="44",
                    position="CF",
                    roster_status="Reassigned to Minors",
                ),
                PlayerHittingStats(
                    player_id=hitter.id,
                    team_id=away.id,
                    season=2026,
                    at_bats=250,
                    hits=75,
                    rbi=41,
                    avg=Decimal(".300"),
                    ops=Decimal(".875"),
                ),
            ]
        )
        db.session.commit()

    response = client.get("/api/teams/145/roster?season=2026")
    roster = response.get_json()["data"]["roster"]

    assert response.status_code == 200
    assert roster["counts"] == {"active": 1, "other": 1, "total": 2}
    active_pitcher = roster["active"]["pitchers"][0]
    other_hitter = roster["other"]["position_players"][0]
    assert active_pitcher["player"]["pitch_hand"] == "Right"
    assert active_pitcher["season_stats"] == {
        "era": "4.11",
        "innings_pitched": "0.0",
    }
    assert other_hitter["season_stats"] == {
        "avg": "0.300",
        "hits": 75,
        "at_bats": 250,
        "rbi": 41,
        "ops": "0.875",
    }


def test_game_detail_api_wraps_linescore_boxscore_and_analysis_inputs(app, client):
    with app.app_context():
        _seed_final_game()
    client.post(
        "/api/auth/register",
        json={"email": "context@example.com", "password": "long-password"},
    )

    response = client.get("/api/games/822786")
    payload = response.get_json()["data"]
    game = payload["game"]

    assert response.status_code == 200
    assert game["away"]["standing"]["division_rank"] == 2
    assert game["home"]["standing"]["division_rank"] == 4
    assert game["decisions"][2]["season_stats"]["saves"] == 8
    assert payload["boxscore"]["away"]["batters"][0]["name"] == "Luis Robert Jr."
    assert payload["boxscore"]["away"]["batters"][0]["player_id"] == 673357
    assert payload["boxscore"]["away"]["batters"][0]["ops"] == ".842"
    assert payload["boxscore"]["away"]["pitchers"][0]["innings"] == "7.0"
    assert payload["boxscore"]["home"]["batters"][0]["name"] == "Bo Bichette"
    assert "players" not in payload["boxscore"]["away"]
    assert "liveData" not in payload
    assert payload["calendar"] == {"connected": False, "added": False}


def test_player_detail_returns_recent_boxscore_appearances(app, client):
    with app.app_context():
        _seed_final_game()
    client.post(
        "/api/auth/register",
        json={"email": "player-recent@example.com", "password": "long-password"},
    )

    response = client.get("/api/players/680732?lang=ja")
    payload = response.get_json()["data"]

    assert response.status_code == 200
    assert payload["recent_appearances"]["game_count"] == 1
    assert payload["recent_appearances"]["hitting"] == []
    appearance = payload["recent_appearances"]["pitching"][0]
    assert appearance["game_pk"] == 822786
    assert appearance["player_id"] == 680732
    assert appearance["opponent"]["abbreviation"] == "TOR"
    assert appearance["innings"] == "7.0"
    assert payload["analyses"] == []


def test_game_active_rosters_filter_appeared_players_for_final_game(app, client):
    with app.app_context():
        _seed_final_game()
        away = db.session.execute(
            db.select(Team).where(Team.mlb_team_id == 145)
        ).scalar_one()
        home = db.session.execute(
            db.select(Team).where(Team.mlb_team_id == 141)
        ).scalar_one()
        appeared_pitcher = db.session.execute(
            db.select(Player).where(Player.mlb_player_id == 680732)
        ).scalar_one()
        appeared_pitcher.pitch_hand = "Right"
        away_catcher = Player(
            mlb_player_id=710001,
            full_name="Away Reserve Catcher",
            primary_position="C",
            pitch_hand="Right",
        )
        home_outfielder = Player(
            mlb_player_id=710002,
            full_name="Home Reserve Outfielder",
            primary_position="RF",
            pitch_hand="Right",
        )
        db.session.add_all([away_catcher, home_outfielder])
        db.session.flush()
        db.session.add_all(
            [
                Roster(
                    team_id=away.id,
                    player_id=appeared_pitcher.id,
                    season=2026,
                    position="P",
                    roster_status="Active",
                ),
                Roster(
                    team_id=away.id,
                    player_id=away_catcher.id,
                    season=2026,
                    position="C",
                    roster_status="Active",
                ),
                Roster(
                    team_id=home.id,
                    player_id=home_outfielder.id,
                    season=2026,
                    position="RF",
                    roster_status="Active",
                ),
                PlayerHittingStats(
                    player_id=away_catcher.id,
                    team_id=away.id,
                    season=2026,
                    at_bats=98,
                    hits=20,
                    rbi=9,
                    avg=Decimal(".204"),
                    ops=Decimal(".612"),
                ),
            ]
        )
        db.session.commit()

    client.post(
        "/api/auth/register",
        json={"email": "game-roster@example.com", "password": "long-password"},
    )
    payload = client.get("/api/games/822786").get_json()["data"]
    away_roster = payload["active_rosters"]["away"]
    home_roster = payload["active_rosters"]["home"]

    assert away_roster["count"] == 1
    assert away_roster["groups"]["pitchers"] == []
    assert away_roster["groups"]["catchers"][0]["player"]["full_name"] == "Away Reserve Catcher"
    assert home_roster["count"] == 1
    assert home_roster["groups"]["outfielders"][0]["player"]["full_name"] == "Home Reserve Outfielder"


def test_scheduled_game_active_rosters_include_all_active_players(app, client):
    with app.app_context():
        _seed_final_game()
        game = db.session.execute(
            db.select(Game).where(Game.game_pk == 822786)
        ).scalar_one()
        game.normalized_status = "SCHEDULED"
        game.home_score = None
        game.away_score = None
        away_pitcher = db.session.execute(
            db.select(Player).where(Player.mlb_player_id == 680732)
        ).scalar_one()
        away_pitcher.pitch_hand = "Right"
        db.session.add(
            Roster(
                team_id=game.away_team_id,
                player_id=away_pitcher.id,
                season=2026,
                position="P",
                roster_status="Active",
            )
        )
        db.session.commit()

    client.post(
        "/api/auth/register",
        json={"email": "pregame-roster@example.com", "password": "long-password"},
    )
    payload = client.get("/api/games/822786").get_json()["data"]

    assert payload["active_rosters"]["away"]["count"] == 1
    assert payload["active_rosters"]["away"]["groups"]["pitchers"][0]["player"]["mlb_player_id"] == 680732


def test_two_way_roster_player_keeps_one_entry_with_pitching_and_hitting_stats(app, client):
    with app.app_context():
        _seed_final_game()
        away = db.session.execute(
            db.select(Team).where(Team.mlb_team_id == 145)
        ).scalar_one()
        two_way = Player(
            mlb_player_id=660271,
            full_name="Shohei Ohtani",
            primary_position="TWP",
            pitch_hand="Right",
        )
        db.session.add(two_way)
        db.session.flush()
        db.session.add_all(
            [
                Roster(
                    team_id=away.id,
                    player_id=two_way.id,
                    season=2026,
                    position="TWP",
                    roster_status="Active",
                ),
                PlayerPitchingStats(
                    player_id=two_way.id,
                    team_id=away.id,
                    season=2026,
                    innings_outs=120,
                    era=Decimal("2.90"),
                ),
                PlayerHittingStats(
                    player_id=two_way.id,
                    team_id=away.id,
                    season=2026,
                    at_bats=300,
                    hits=90,
                    rbi=60,
                    avg=Decimal(".300"),
                    ops=Decimal(".950"),
                ),
            ]
        )
        db.session.commit()

    roster = client.get("/api/teams/145/roster?season=2026").get_json()["data"]["roster"]
    ohtani = roster["active"]["pitchers"][0]

    assert roster["counts"]["total"] == 1
    assert ohtani["is_two_way"] is True
    assert ohtani["season_stats"] == {
        "era": "2.90",
        "innings_pitched": "40.0",
        "avg": "0.300",
        "hits": 90,
        "at_bats": 300,
        "rbi": 60,
        "ops": "0.950",
    }


def test_team_month_schedule_returns_games_without_roster(app, client):
    with app.app_context():
        _seed_final_game()
        game = db.session.execute(
            db.select(Game).where(Game.game_pk == 822786)
        ).scalar_one()
        month = game.start_time_jst.strftime("%Y-%m")
    client.post(
        "/api/auth/register",
        json={"email": "team-calendar@example.com", "password": "long-password"},
    )

    response = client.get(f"/api/teams/145/schedule?month={month}")
    payload = response.get_json()["data"]

    assert response.status_code == 200
    assert payload["month"] == month
    assert payload["games"][0]["game_pk"] == 822786
    assert "roster" not in payload


def test_team_month_schedule_rejects_invalid_month(app, client):
    with app.app_context():
        _seed_final_game()
    client.post(
        "/api/auth/register",
        json={"email": "team-calendar-invalid@example.com", "password": "long-password"},
    )

    response = client.get("/api/teams/145/schedule?month=2026-99")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_MONTH"


def test_game_detail_api_returns_calendar_connection_and_added_state(app, client):
    with app.app_context():
        _seed_final_game()
    client.post(
        "/api/auth/register",
        json={"email": "calendar-state@example.com", "password": "long-password"},
    )
    with app.app_context():
        user = db.session.execute(
            db.select(User).where(User.email == "calendar-state@example.com")
        ).scalar_one()
        db.session.add(
            GoogleCalendarToken(
                user_id=user.id,
                encrypted_access_token="encrypted-access",
                encrypted_refresh_token="encrypted-refresh",
                scopes="https://www.googleapis.com/auth/calendar.events",
            )
        )
        db.session.add(
            CalendarGameEvent(
                user_id=user.id,
                game_pk=822786,
                google_event_id="calendar-event-id",
            )
        )
        db.session.commit()

    response = client.get("/api/games/822786")

    assert response.status_code == 200
    assert response.get_json()["data"]["calendar"] == {
        "connected": True,
        "added": True,
    }


def test_team_detail_api_returns_centered_seven_day_game_window(app, client):
    with app.app_context():
        _seed_final_game()
    client.post(
        "/api/auth/register",
        json={"email": "team-calendar@example.com", "password": "long-password"},
    )

    response = client.get("/api/teams/145")
    payload = response.get_json()["data"]
    today = datetime.now(timezone.utc).astimezone(
        ZoneInfo("Asia/Tokyo")
    ).date()

    assert response.status_code == 200
    assert payload["game_window"]["start_date"] == (today - timedelta(days=3)).isoformat()
    assert payload["game_window"]["today"] == today.isoformat()
    assert payload["game_window"]["end_date"] == (today + timedelta(days=3)).isoformat()
    assert payload["games"][0]["game_pk"] == 822786
    assert [item["code"] for item in payload["games"][0]["decisions"]] == ["W", "L", "S"]


def test_month_schedule_api_filters_without_html(app, client):
    with app.app_context():
        _seed_final_game()

    now = datetime.now(timezone.utc)
    month = now.astimezone().strftime("%Y-%m")
    response = client.get(f"/api/games?month={month}&team=145")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["meta"]["month"] == month
    assert payload["meta"]["team"] == 145
    assert payload["data"][0]["away"]["team"]["abbreviation"] == "CWS"


def test_date_schedule_api_filters_by_jst_calendar_date(app, client):
    with app.app_context():
        _seed_final_game()

    selected_date = datetime.now(timezone.utc).astimezone(
        ZoneInfo("Asia/Tokyo")
    ).date().isoformat()
    response = client.get(f"/api/games?date={selected_date}&team=145")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["meta"]["date"] == selected_date
    assert payload["meta"]["team"] == 145
    assert payload["data"][0]["away"]["team"]["abbreviation"] == "CWS"
