import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.extensions import db
from app.models import (
    ApiResponse,
    Game,
    GameSnapshot,
    PlayerHittingStats,
    PlayerPitchingStats,
    Roster,
    Standing,
    Team,
)
from app.services.mlb_sync_service import MLBSyncService


FIXTURES = Path(__file__).parents[1] / "fixtures"


class FixtureClient:
    def teams(self):
        return json.loads((FIXTURES / "teams.json").read_text())

    def standings(self, _season):
        return json.loads((FIXTURES / "standings.json").read_text())


class DecisionFixtureClient(FixtureClient):
    pitcher_teams = {
        680732: 145,
        702056: 141,
        691799: 145,
    }

    def schedule(self, _start, _end):
        return json.loads((FIXTURES / "game_final.json").read_text())

    def player_stats(self, player_id, _season):
        stats = {
            680732: {"wins": 7, "losses": 8, "era": "4.11"},
            702056: {"wins": 3, "losses": 5, "era": "4.37"},
            691799: {"wins": 2, "losses": 1, "saves": 8, "era": "2.18"},
        }[player_id]
        return {
            "stats": [
                {
                    "group": {"displayName": "pitching"},
                    "splits": [
                        {
                            "team": {"id": self.pitcher_teams[player_id]},
                            "stat": stats,
                        }
                    ],
                }
            ]
        }

    def boxscore(self, _game_pk):
        return json.loads((FIXTURES / "boxscore.json").read_text())


class ScheduledFixtureClient(DecisionFixtureClient):
    def schedule(self, _start, _end):
        payload = super().schedule(_start, _end)
        game = payload["dates"][0]["games"][0]
        game["status"] = {
            "abstractGameState": "Preview",
            "detailedState": "Scheduled",
        }
        game.pop("decisions", None)
        game.pop("linescore", None)
        for side in ("away", "home"):
            game["teams"][side].pop("score", None)
            game["teams"][side].pop("isWinner", None)
        return payload


class RescheduledFixtureClient(DecisionFixtureClient):
    def schedule(self, start, _end):
        payload = super().schedule(start, _end)
        game = payload["dates"][0]["games"][0]
        if start == "2026-07-07":
            game["gameDate"] = "2026-07-07T18:15:00Z"
            game["officialDate"] = "2026-07-07"
            game["rescheduledFrom"] = "2026-05-05T23:45:00Z"
            return payload

        game["gameDate"] = "2026-05-05T23:45:00Z"
        game["officialDate"] = "2026-07-07"
        game["rescheduleDate"] = "2026-07-07T18:15:00Z"
        game["status"] = {
            "abstractGameState": "Final",
            "codedGameState": "D",
            "detailedState": "Postponed",
            "statusCode": "DI",
        }
        game.pop("decisions", None)
        game.pop("linescore", None)
        for side in ("away", "home"):
            game["teams"][side].pop("score", None)
            game["teams"][side].pop("isWinner", None)
        return payload


class LiveFixtureClient(FixtureClient):
    def live_feed(self, _game_pk):
        payload = json.loads((FIXTURES / "game_live.json").read_text())
        payload["liveData"]["boxscore"] = json.loads(
            (FIXTURES / "boxscore.json").read_text()
        )
        return payload


class RosterFixtureClient:
    def __init__(self):
        self.calls = []

    @staticmethod
    def _person(player_id, name, position, stats):
        return {
            "id": player_id,
            "fullName": name,
            "active": True,
            "primaryPosition": {"abbreviation": position},
            "pitchHand": {"description": "Left" if position == "P" else "Right"},
            "batSide": {"description": "Right"},
            "stats": stats,
        }

    def roster(self, _team_id, _season, roster_type="active", *, hydrate_stats=False):
        self.calls.append((roster_type, hydrate_stats))
        pitching = [
            {
                "group": {"displayName": "pitching"},
                "splits": [
                    {
                        "stat": {
                            "gamesPlayed": 20,
                            "gamesStarted": 18,
                            "inningsPitched": "101.2",
                            "era": "3.14",
                            "whip": "1.08",
                        }
                    }
                ],
            }
        ]
        hitting = [
            {
                "group": {"displayName": "hitting"},
                "splits": [
                    {
                        "stat": {
                            "gamesPlayed": 80,
                            "atBats": 300,
                            "hits": 87,
                            "rbi": 46,
                            "avg": ".290",
                            "ops": ".840",
                        }
                    }
                ],
            }
        ]
        rows = [
            {
                "person": self._person(9001, "Active Pitcher", "P", pitching),
                "jerseyNumber": "18",
                "position": {"abbreviation": "P"},
                "status": {"description": "Active"},
            },
            {
                "person": self._person(9002, "Active Hitter", "SS", hitting),
                "jerseyNumber": "7",
                "position": {"abbreviation": "SS"},
                "status": {"description": "Active"},
            },
        ]
        if roster_type == "40Man":
            rows.append(
                {
                    "person": self._person(9003, "Inactive Hitter", "OF", hitting),
                    "jerseyNumber": "62",
                    "position": {"abbreviation": "OF"},
                    "status": {"description": "Reassigned to Minors"},
                }
            )
        if not hydrate_stats:
            for row in rows:
                row["person"].pop("stats", None)
        return {"roster": rows}


def test_sync_current_games_cli_uses_a_short_jst_window(app, monkeypatch):
    calls = []

    class StubService:
        def sync_schedule(self, start, end):
            calls.append(("schedule", start, end))
            return 12

        def sync_live_games(self):
            calls.append(("live",))
            return 3

    monkeypatch.setattr("app.commands.sync_commands._service", StubService)

    result = app.test_cli_runner().invoke(
        args=["sync-current-games", "--lookback-days", "2"]
    )

    assert result.exit_code == 0
    assert "schedule=12, live=3" in result.output
    _, start, end = calls[0]
    assert end - start == timedelta(days=2)
    assert calls[1] == ("live",)


def test_bootstrap_marker_releases_waiting_worker(app):
    runner = app.test_cli_runner()

    started = runner.invoke(args=["mark-bootstrap-started", "--season", "2026"])
    completed = runner.invoke(args=["mark-bootstrap-complete", "--season", "2026"])
    waiting = runner.invoke(
        args=[
            "wait-for-bootstrap",
            "--season",
            "2026",
            "--poll-seconds",
            "1",
            "--timeout-seconds",
            "1",
        ]
    )

    assert started.exit_code == 0
    assert completed.exit_code == 0
    assert waiting.exit_code == 0
    assert "bootstrap ready: season=2026" in waiting.output
    with app.app_context():
        marker = db.session.execute(
            db.select(ApiResponse).where(
                ApiResponse.cache_key == "internal:bootstrap:2026"
            )
        ).scalar_one()
        assert marker.payload["state"] == "complete"


def test_roster_sync_merges_active_and_40man_and_stores_hydrated_stats(app):
    with app.app_context():
        team = Team(
            mlb_team_id=119,
            name="Los Angeles Dodgers",
            abbreviation="LAD",
            league="NL",
            division="NL West",
        )
        db.session.add(team)
        db.session.commit()
        client = RosterFixtureClient()
        service = MLBSyncService(client, throttle_seconds=0)

        assert service.sync_rosters(2026) == (3, 3)

        entries = db.session.execute(
            db.select(Roster).order_by(Roster.player_id)
        ).scalars().all()
        assert [entry.roster_status for entry in entries] == [
            "Active",
            "Active",
            "Reassigned to Minors",
        ]
        assert client.calls == [("40Man", True), ("active", False)]
        pitching = db.session.execute(db.select(PlayerPitchingStats)).scalar_one()
        hitting = db.session.execute(
            db.select(PlayerHittingStats).order_by(PlayerHittingStats.player_id)
        ).scalars().all()
        assert pitching.innings_pitched == "101.2"
        assert str(pitching.era) == "3.14"
        assert len(hitting) == 2
        assert (hitting[0].hits, hitting[0].at_bats, str(hitting[0].ops)) == (
            87,
            300,
            "0.840",
        )


def test_team_upsert_is_idempotent(app):
    with app.app_context():
        service = MLBSyncService(FixtureClient(), throttle_seconds=0)
        assert service.sync_teams() == 30
        assert service.sync_teams() == 30
        assert db.session.scalar(db.select(db.func.count(Team.id))) == 30


def test_standings_fixture_parsing(app):
    with app.app_context():
        service = MLBSyncService(FixtureClient(), throttle_seconds=0)
        service.sync_teams()
        assert service.sync_standings(2026) == 30
        first = db.session.execute(
            db.select(Standing).order_by(Standing.division_rank).limit(1)
        ).scalar_one()
        assert first.wins >= 0
        assert first.home_wins + first.away_wins == first.wins
        assert first.streak


def test_final_game_syncs_decisions_and_pitcher_season_stats(app):
    with app.app_context():
        service = MLBSyncService(DecisionFixtureClient(), throttle_seconds=0)
        service.sync_teams()

        assert service.sync_schedule(date(2026, 7, 19), date(2026, 7, 19)) == 1

        game = db.session.execute(
            db.select(Game).where(Game.game_pk == 822786)
        ).scalar_one()
        assert game.winning_pitcher.full_name == "Sean Burke"
        assert game.losing_pitcher.full_name == "Trey Yesavage"
        assert game.save_pitcher.full_name == "Grant Taylor"

        stats = db.session.execute(
            db.select(PlayerPitchingStats)
            .where(PlayerPitchingStats.season == 2026)
            .order_by(PlayerPitchingStats.player_id)
        ).scalars().all()
        assert len(stats) == 3
        winner_stats = next(
            row for row in stats if row.player_id == game.winning_pitcher_id
        )
        assert (winner_stats.wins, winner_stats.losses) == (7, 8)
        assert str(winner_stats.era) == "4.11"
        assert db.session.scalar(
            db.select(db.func.count()).select_from(GameSnapshot).where(
                GameSnapshot.game_pk == game.game_pk,
                GameSnapshot.snapshot_type == "BOX_SCORE",
            )
        ) == 1


def test_scheduled_game_syncs_probable_pitcher_season_stats(app):
    with app.app_context():
        service = MLBSyncService(ScheduledFixtureClient(), throttle_seconds=0)
        service.sync_teams()

        assert service.sync_schedule(date(2026, 7, 19), date(2026, 7, 19)) == 1

        game = db.session.execute(
            db.select(Game).where(Game.game_pk == 822786)
        ).scalar_one()
        stats = db.session.execute(
            db.select(PlayerPitchingStats)
            .where(PlayerPitchingStats.season == 2026)
            .order_by(PlayerPitchingStats.player_id)
        ).scalars().all()
        assert len(stats) == 2
        assert {
            (row.player_id, row.wins, row.losses, str(row.era))
            for row in stats
        } == {
            (game.probable_away_pitcher_id, 7, 8, "4.11"),
            (game.probable_home_pitcher_id, 3, 5, "4.37"),
        }


def test_old_postponed_alias_cannot_overwrite_rescheduled_game(app):
    with app.app_context():
        service = MLBSyncService(RescheduledFixtureClient(), throttle_seconds=0)
        service.sync_teams()

        assert service.sync_schedule(date(2026, 7, 7), date(2026, 7, 7)) == 1
        assert service.sync_schedule(date(2026, 5, 5), date(2026, 5, 5)) == 1

        game = db.session.execute(
            db.select(Game).where(Game.game_pk == 822786)
        ).scalar_one()
        assert game.normalized_status == "FINAL"
        assert game.detailed_status == "Final"
        assert game.start_time_utc.date() == date(2026, 7, 7)
        assert game.away_score is not None
        assert game.home_score is not None


def test_live_sync_stores_current_boxscore(app):
    with app.app_context():
        service = MLBSyncService(LiveFixtureClient(), throttle_seconds=0)
        service.sync_teams()
        away = db.session.execute(
            db.select(Team).where(Team.mlb_team_id == 145)
        ).scalar_one()
        home = db.session.execute(
            db.select(Team).where(Team.mlb_team_id == 141)
        ).scalar_one()
        game = Game(
            game_pk=822786,
            season=2026,
            game_type="R",
            official_date=date(2026, 7, 19),
            start_time_utc=datetime(2026, 7, 19, 16, 15, tzinfo=timezone.utc),
            start_time_jst=datetime(2026, 7, 20, 1, 15, tzinfo=timezone.utc),
            home_team_id=home.id,
            away_team_id=away.id,
            normalized_status="LIVE",
        )
        db.session.add(game)
        db.session.commit()

        assert service.sync_live_games() == 1
        boxscore = db.session.execute(
            db.select(GameSnapshot).where(
                GameSnapshot.game_pk == game.game_pk,
                GameSnapshot.snapshot_type == "BOX_SCORE",
            )
        ).scalar_one()
        assert boxscore.inning == 7
        assert boxscore.payload["teams"]["away"]["players"]
