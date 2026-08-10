import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.extensions import db
from app.models import (
    ApiResponse,
    Game,
    GameSnapshot,
    Player,
    PlayerHittingStats,
    PlayerPitchingStats,
    Roster,
    Standing,
    Team,
    TeamSeasonStats,
)
from app.services.game_status_service import GameStatus, normalize_game_status
from app.services.mlb_client import MLBClient
from app.services.statistics_service import innings_to_outs
from app.services.time_service import parse_mlb_datetime, to_jst


logger = logging.getLogger(__name__)


def _int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _source_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class MLBSyncService:
    def __init__(self, client: MLBClient, throttle_seconds: float = 0.05):
        self.client = client
        self.throttle_seconds = throttle_seconds

    @staticmethod
    def _upsert(model, key_values: dict, values: dict):
        record = db.session.execute(db.select(model).filter_by(**key_values)).scalar_one_or_none()
        if record is None:
            record = model(**key_values, **values)
            db.session.add(record)
            db.session.flush()
        else:
            for key, value in values.items():
                setattr(record, key, value)
        return record

    def _cache_payload(self, key: str, endpoint: str, payload: dict, ttl_minutes: int) -> None:
        now = datetime.now(timezone.utc)
        values = {
            "endpoint": endpoint,
            "params_hash": _source_hash({"key": key}),
            "payload": payload,
            "fetched_at": now,
            "expires_at": now + timedelta(minutes=ttl_minutes),
        }
        self._upsert(ApiResponse, {"cache_key": key}, values)

    def sync_teams(self) -> int:
        payload = self.client.teams()
        count = 0
        with db.session.begin_nested():
            for raw in payload.get("teams", []):
                league = raw.get("league") or {}
                division = raw.get("division") or {}
                if league.get("id") not in {103, 104}:
                    continue
                team_id = _int(raw.get("id"))
                if not team_id:
                    logger.warning("Skipping team without id: %r", raw.get("name"))
                    continue
                self._upsert(
                    Team,
                    {"mlb_team_id": team_id},
                    {
                        "name": raw.get("name") or f"MLB Team {team_id}",
                        "abbreviation": raw.get("abbreviation") or "—",
                        "league": league.get("abbreviation")
                        or ("AL" if league.get("id") == 103 else "NL"),
                        "division": division.get("nameShort")
                        or division.get("name")
                        or "Unknown",
                        "logo_url": (
                            f"https://www.mlbstatic.com/team-logos/{team_id}.svg"
                        ),
                        "venue_name": (raw.get("venue") or {}).get("name"),
                    },
                )
                count += 1
            self._cache_payload("teams:mlb", "teams", payload, 24 * 60)
        db.session.commit()
        logger.info("Synced %s MLB teams", count)
        return count

    def _upsert_person(self, raw: dict | None) -> Player | None:
        raw = raw or {}
        player_id = _int(raw.get("id"))
        if not player_id:
            return None
        return self._upsert(
            Player,
            {"mlb_player_id": player_id},
            {
                "full_name": raw.get("fullName") or f"MLB Player {player_id}",
                "primary_position": (raw.get("primaryPosition") or {}).get("abbreviation")
                or (raw.get("primaryPosition") or {}).get("name"),
                "bat_side": (raw.get("batSide") or {}).get("description"),
                "pitch_hand": (raw.get("pitchHand") or {}).get("description"),
                "birth_date": _date(raw.get("birthDate")),
                "active": bool(raw.get("active", True)),
            },
        )

    def sync_schedule(self, start: date, end: date) -> int:
        payload = self.client.schedule(start.isoformat(), end.isoformat())
        teams = {
            team.mlb_team_id: team
            for team in db.session.execute(db.select(Team)).scalars().all()
        }
        count = 0
        season_pitchers: dict[tuple[int, int, int], tuple[int, int]] = {}
        boxscore_game_pks: set[int] = set()
        with db.session.begin_nested():
            for day in payload.get("dates", []):
                for raw in day.get("games", []):
                    game_pk = _int(raw.get("gamePk"))
                    raw_teams = raw.get("teams") or {}
                    home_raw = (raw_teams.get("home") or {}).get("team") or {}
                    away_raw = (raw_teams.get("away") or {}).get("team") or {}
                    home = teams.get(_int(home_raw.get("id")))
                    away = teams.get(_int(away_raw.get("id")))
                    if not game_pk or not home or not away or not raw.get("gameDate"):
                        logger.warning("Skipping incomplete game payload: %r", game_pk)
                        continue
                    start_utc = parse_mlb_datetime(raw["gameDate"])
                    home_pitcher = self._upsert_person(
                        (raw_teams.get("home") or {}).get("probablePitcher")
                    )
                    away_pitcher = self._upsert_person(
                        (raw_teams.get("away") or {}).get("probablePitcher")
                    )
                    decisions = raw.get("decisions") or {}
                    winning_pitcher = self._upsert_person(decisions.get("winner"))
                    losing_pitcher = self._upsert_person(decisions.get("loser"))
                    save_pitcher = self._upsert_person(decisions.get("save"))
                    linescore = raw.get("linescore") or {}
                    status = raw.get("status") or {}
                    normalized_status = normalize_game_status(status).value
                    existing_game = db.session.execute(
                        db.select(Game).where(Game.game_pk == game_pk)
                    ).scalar_one_or_none()
                    reschedule_start = None
                    if raw.get("rescheduleDate"):
                        try:
                            reschedule_start = parse_mlb_datetime(raw["rescheduleDate"])
                        except (TypeError, ValueError):
                            logger.warning(
                                "Ignoring invalid rescheduleDate for game %s: %r",
                                game_pk,
                                raw.get("rescheduleDate"),
                            )
                    is_obsolete_postponed_alias = (
                        normalized_status == GameStatus.POSTPONED.value
                        and reschedule_start is not None
                        and not raw.get("rescheduledFrom")
                        and existing_game is not None
                        and existing_game.normalized_status
                        != GameStatus.POSTPONED.value
                        and existing_game.start_time_utc.date()
                        >= reschedule_start.date()
                    )
                    if is_obsolete_postponed_alias:
                        logger.info(
                            "Keeping canonical rescheduled occurrence for game %s; "
                            "ignored postponed alias at %s",
                            game_pk,
                            raw.get("gameDate"),
                        )
                        count += 1
                        continue
                    season = _int(raw.get("season"), start_utc.year)
                    for pitcher, team in (
                        (away_pitcher, away),
                        (home_pitcher, home),
                    ):
                        if pitcher and team:
                            season_pitchers[
                                (pitcher.id, team.id, season)
                            ] = (pitcher.mlb_player_id, team.mlb_team_id)
                    home_is_winner = bool((raw_teams.get("home") or {}).get("isWinner"))
                    winning_team = home if home_is_winner else away
                    losing_team = away if home_is_winner else home
                    for pitcher, team in (
                        (winning_pitcher, winning_team),
                        (losing_pitcher, losing_team),
                        (save_pitcher, winning_team),
                    ):
                        if pitcher and team:
                            season_pitchers[
                                (pitcher.id, team.id, season)
                            ] = (pitcher.mlb_player_id, team.mlb_team_id)
                    self._upsert(
                        Game,
                        {"game_pk": game_pk},
                        {
                            "season": season,
                            "game_type": raw.get("gameType"),
                            "official_date": _date(raw.get("officialDate"))
                            or start_utc.date(),
                            "start_time_utc": start_utc,
                            "start_time_jst": to_jst(start_utc),
                            "home_team_id": home.id,
                            "away_team_id": away.id,
                            "home_score": _int((raw_teams.get("home") or {}).get("score")),
                            "away_score": _int((raw_teams.get("away") or {}).get("score")),
                            "abstract_status": status.get("abstractGameState"),
                            "detailed_status": status.get("detailedState"),
                            "normalized_status": normalized_status,
                            "current_inning": _int(linescore.get("currentInning")),
                            "inning_half": linescore.get("inningHalf")
                            or linescore.get("inningState"),
                            "venue_name": (raw.get("venue") or {}).get("name"),
                            "probable_home_pitcher_id": home_pitcher.id if home_pitcher else None,
                            "probable_away_pitcher_id": away_pitcher.id if away_pitcher else None,
                            "winning_pitcher_id": (
                                winning_pitcher.id if winning_pitcher else None
                            ),
                            "losing_pitcher_id": (
                                losing_pitcher.id if losing_pitcher else None
                            ),
                            "save_pitcher_id": save_pitcher.id if save_pitcher else None,
                        },
                    )
                    if normalized_status == GameStatus.FINAL.value:
                        boxscore_game_pks.add(game_pk)
                    if linescore:
                        trimmed = {
                            "innings": linescore.get("innings", []),
                            "teams": linescore.get("teams", {}),
                            "offense": linescore.get("offense", {}),
                            "defense": linescore.get("defense", {}),
                        }
                        self._upsert(
                            GameSnapshot,
                            {
                                "game_pk": game_pk,
                                "snapshot_type": "LINESCORE",
                                "source_hash": _source_hash(trimmed),
                            },
                            {
                                "inning": _int(linescore.get("currentInning")),
                                "payload": trimmed,
                                "fetched_at": datetime.now(timezone.utc),
                            },
                        )
                    count += 1
            self._cache_payload(
                f"schedule:{start}:{end}",
                "schedule",
                payload,
                5,
            )
        db.session.commit()
        pitcher_stats_count = self._sync_pitcher_stats(season_pitchers)
        boxscore_count = self._sync_boxscores(boxscore_game_pks)
        logger.info("Synced %s games from %s to %s", count, start, end)
        logger.info("Synced %s probable/decision pitcher stat lines", pitcher_stats_count)
        logger.info("Synced %s final game boxscores", boxscore_count)
        return count

    @staticmethod
    def _split_record(raw: dict, record_type: str) -> dict:
        split_records = (raw.get("records") or {}).get("splitRecords") or []
        return next((item for item in split_records if item.get("type") == record_type), {})

    def sync_standings(self, season: int) -> int:
        payload = self.client.standings(season)
        teams = {
            team.mlb_team_id: team
            for team in db.session.execute(db.select(Team)).scalars().all()
        }
        count = 0
        with db.session.begin_nested():
            for record in payload.get("records", []):
                division = record.get("division") or {}
                for raw in record.get("teamRecords", []):
                    team_raw = raw.get("team") or {}
                    team = teams.get(_int(team_raw.get("id")))
                    if team is None:
                        logger.warning("Standing references unsynced team %r", team_raw.get("id"))
                        continue
                    if division.get("nameShort"):
                        team.division = division["nameShort"]
                    league_record = raw.get("leagueRecord") or {}
                    home = self._split_record(raw, "home")
                    away = self._split_record(raw, "away")
                    last_ten = self._split_record(raw, "lastTen")
                    self._upsert(
                        Standing,
                        {"season": season, "team_id": team.id},
                        {
                            "wins": _int(league_record.get("wins"), 0),
                            "losses": _int(league_record.get("losses"), 0),
                            "winning_percentage": _decimal(league_record.get("pct")),
                            "games_back": raw.get("gamesBack"),
                            "division_rank": _int(raw.get("divisionRank")),
                            "league_rank": _int(raw.get("leagueRank")),
                            "home_wins": _int(home.get("wins"), 0),
                            "home_losses": _int(home.get("losses"), 0),
                            "away_wins": _int(away.get("wins"), 0),
                            "away_losses": _int(away.get("losses"), 0),
                            "last_ten_wins": _int(last_ten.get("wins"), 0),
                            "last_ten_losses": _int(last_ten.get("losses"), 0),
                            "streak": (raw.get("streak") or {}).get("streakCode"),
                            "runs_scored": _int(raw.get("runsScored"), 0),
                            "runs_allowed": _int(raw.get("runsAllowed"), 0),
                        },
                    )
                    count += 1
            self._cache_payload(
                f"standings:{season}", "standings", payload, 20
            )
        db.session.commit()
        logger.info("Synced %s standings rows", count)
        return count

    def sync_rosters(self, season: int) -> tuple[int, int]:
        teams = db.session.execute(db.select(Team).order_by(Team.id)).scalars().all()
        player_count = roster_count = 0
        for team in teams:
            try:
                payload = self.client.roster(
                    team.mlb_team_id,
                    season,
                    "40Man",
                    hydrate_stats=True,
                )
                active_payload = self.client.roster(
                    team.mlb_team_id,
                    season,
                    "active",
                )
                active_ids = {
                    _int((raw.get("person") or {}).get("id"))
                    for raw in active_payload.get("roster", [])
                }
                active_ids.discard(None)
                roster_by_player = {
                    _int((raw.get("person") or {}).get("id")): raw
                    for raw in payload.get("roster", [])
                    if _int((raw.get("person") or {}).get("id"))
                }
                for raw in active_payload.get("roster", []):
                    player_id = _int((raw.get("person") or {}).get("id"))
                    if player_id and player_id not in roster_by_player:
                        roster_by_player[player_id] = raw
                if not roster_by_player:
                    logger.warning("MLB returned an empty roster for %s", team.name)
                    continue
                with db.session.begin_nested():
                    synced_player_ids = set()
                    for mlb_player_id, raw in roster_by_player.items():
                        person_raw = raw.get("person") or {}
                        player = self._upsert_person(person_raw)
                        if player is None:
                            continue
                        synced_player_ids.add(player.id)
                        self._upsert(
                            Roster,
                            {"team_id": team.id, "player_id": player.id, "season": season},
                            {
                                "jersey_number": raw.get("jerseyNumber"),
                                "position": (raw.get("position") or {}).get("abbreviation")
                                or (raw.get("position") or {}).get("name"),
                                "roster_status": (
                                    "Active"
                                    if mlb_player_id in active_ids
                                    else (raw.get("status") or {}).get("description")
                                    or "40-man roster"
                                ),
                            },
                        )
                        groups = self._stats_by_group(person_raw)
                        hitting = groups.get("hitting")
                        if hitting:
                            self._upsert(
                                PlayerHittingStats,
                                {
                                    "player_id": player.id,
                                    "team_id": team.id,
                                    "season": season,
                                },
                                self._hitting_values(hitting),
                            )
                        pitching = groups.get("pitching")
                        if pitching:
                            self._upsert(
                                PlayerPitchingStats,
                                {
                                    "player_id": player.id,
                                    "team_id": team.id,
                                    "season": season,
                                },
                                self._pitching_values(pitching),
                            )
                        player_count += 1
                        roster_count += 1
                    if synced_player_ids:
                        db.session.execute(
                            db.delete(Roster).where(
                                Roster.team_id == team.id,
                                Roster.season == season,
                                ~Roster.player_id.in_(synced_player_ids),
                            )
                        )
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                logger.error("Roster sync failed for %s: %s", team.name, exc)
            time.sleep(self.throttle_seconds)
        return player_count, roster_count

    @staticmethod
    def _stats_by_group(payload: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for block in payload.get("stats", []):
            group = (block.get("group") or {}).get("displayName", "").lower()
            splits = block.get("splits") or []
            if group and splits:
                result[group] = splits[0].get("stat") or {}
        return result

    @staticmethod
    def _stat_for_team(payload: dict, group_name: str, mlb_team_id: int) -> dict:
        fallback = {}
        for block in payload.get("stats", []):
            group = (block.get("group") or {}).get("displayName", "").lower()
            if group != group_name:
                continue
            for split in block.get("splits") or []:
                stat = split.get("stat") or {}
                fallback = fallback or stat
                if _int((split.get("team") or {}).get("id")) == mlb_team_id:
                    return stat
        return fallback

    @staticmethod
    def _pitching_values(pitching: dict) -> dict:
        return {
            "games_played": _int(pitching.get("gamesPlayed")),
            "games_started": _int(pitching.get("gamesStarted")),
            "wins": _int(pitching.get("wins")),
            "losses": _int(pitching.get("losses")),
            "saves": _int(pitching.get("saves")),
            "innings_outs": innings_to_outs(pitching.get("inningsPitched")),
            "hits": _int(pitching.get("hits")),
            "earned_runs": _int(pitching.get("earnedRuns")),
            "home_runs": _int(pitching.get("homeRuns")),
            "walks": _int(pitching.get("baseOnBalls")),
            "strikeouts": _int(pitching.get("strikeOuts")),
            "era": _decimal(pitching.get("era")),
            "whip": _decimal(pitching.get("whip")),
        }

    @staticmethod
    def _hitting_values(hitting: dict) -> dict:
        return {
            "games_played": _int(hitting.get("gamesPlayed")),
            "plate_appearances": _int(hitting.get("plateAppearances")),
            "at_bats": _int(hitting.get("atBats")),
            "runs": _int(hitting.get("runs")),
            "hits": _int(hitting.get("hits")),
            "doubles": _int(hitting.get("doubles")),
            "triples": _int(hitting.get("triples")),
            "home_runs": _int(hitting.get("homeRuns")),
            "rbi": _int(hitting.get("rbi")),
            "walks": _int(hitting.get("baseOnBalls")),
            "strikeouts": _int(hitting.get("strikeOuts")),
            "stolen_bases": _int(hitting.get("stolenBases")),
            "avg": _decimal(hitting.get("avg")),
            "obp": _decimal(hitting.get("obp")),
            "slg": _decimal(hitting.get("slg")),
            "ops": _decimal(hitting.get("ops")),
        }

    def _sync_pitcher_stats(
        self,
        pitchers: dict[tuple[int, int, int], tuple[int, int]],
    ) -> int:
        count = 0
        stale_before = datetime.now(timezone.utc) - timedelta(minutes=30)
        for (player_id, team_id, season), (mlb_player_id, mlb_team_id) in pitchers.items():
            existing = db.session.execute(
                db.select(PlayerPitchingStats).where(
                    PlayerPitchingStats.player_id == player_id,
                    PlayerPitchingStats.team_id == team_id,
                    PlayerPitchingStats.season == season,
                )
            ).scalar_one_or_none()
            if existing and existing.updated_at:
                updated_at = existing.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if updated_at >= stale_before:
                    continue
            try:
                payload = self.client.player_stats(mlb_player_id, season)
                pitching = self._stat_for_team(payload, "pitching", mlb_team_id)
                if not pitching:
                    logger.warning(
                        "No pitching season stats for pitcher %s", mlb_player_id
                    )
                    continue
                with db.session.begin_nested():
                    self._upsert(
                        PlayerPitchingStats,
                        {
                            "player_id": player_id,
                            "team_id": team_id,
                            "season": season,
                        },
                        self._pitching_values(pitching),
                    )
                db.session.commit()
                count += 1
            except Exception as exc:
                db.session.rollback()
                logger.error(
                    "Pitcher stats sync failed for %s: %s",
                    mlb_player_id,
                    exc,
                )
            time.sleep(self.throttle_seconds)
        return count

    def _sync_boxscores(self, game_pks: set[int]) -> int:
        count = 0
        for game_pk in sorted(game_pks):
            existing = db.session.execute(
                db.select(GameSnapshot.id).where(
                    GameSnapshot.game_pk == game_pk,
                    GameSnapshot.snapshot_type == "BOX_SCORE",
                )
            ).first()
            if existing:
                continue
            try:
                payload = self.client.boxscore(game_pk)
                if not (payload.get("teams") or {}):
                    continue
                with db.session.begin_nested():
                    self._upsert(
                        GameSnapshot,
                        {
                            "game_pk": game_pk,
                            "snapshot_type": "BOX_SCORE",
                            "source_hash": _source_hash(payload),
                        },
                        {
                            "payload": payload,
                            "fetched_at": datetime.now(timezone.utc),
                        },
                    )
                db.session.commit()
                count += 1
            except Exception as exc:
                db.session.rollback()
                logger.error("Boxscore sync failed for game %s: %s", game_pk, exc)
            time.sleep(self.throttle_seconds)
        return count

    def sync_team_stats(self, season: int) -> int:
        teams = db.session.execute(db.select(Team).order_by(Team.id)).scalars().all()
        count = 0
        for team in teams:
            try:
                groups = self._stats_by_group(
                    self.client.team_stats(team.mlb_team_id, season)
                )
                hitting = groups.get("hitting", {})
                pitching = groups.get("pitching", {})
                with db.session.begin_nested():
                    self._upsert(
                        TeamSeasonStats,
                        {"team_id": team.id, "season": season},
                        {
                            "games_played": _int(hitting.get("gamesPlayed")),
                            "batting_avg": _decimal(hitting.get("avg")),
                            "obp": _decimal(hitting.get("obp")),
                            "slg": _decimal(hitting.get("slg")),
                            "ops": _decimal(hitting.get("ops")),
                            "runs": _int(hitting.get("runs")),
                            "hits": _int(hitting.get("hits")),
                            "home_runs": _int(hitting.get("homeRuns")),
                            "batting_strikeouts": _int(hitting.get("strikeOuts")),
                            "batting_walks": _int(hitting.get("baseOnBalls")),
                            "era": _decimal(pitching.get("era")),
                            "whip": _decimal(pitching.get("whip")),
                            "wins": _int(pitching.get("wins")),
                            "losses": _int(pitching.get("losses")),
                            "saves": _int(pitching.get("saves")),
                            "pitching_strikeouts": _int(pitching.get("strikeOuts")),
                            "pitching_walks": _int(pitching.get("baseOnBalls")),
                            "home_runs_allowed": _int(pitching.get("homeRuns")),
                        },
                    )
                db.session.commit()
                count += 1
            except Exception as exc:
                db.session.rollback()
                logger.error("Team stats sync failed for %s: %s", team.name, exc)
            time.sleep(self.throttle_seconds)
        return count

    def sync_player_stats(self, season: int) -> int:
        entries = db.session.execute(
            db.select(Roster).where(Roster.season == season).order_by(Roster.id)
        ).scalars().all()
        count = 0
        for entry in entries:
            try:
                groups = self._stats_by_group(
                    self.client.player_stats(entry.player.mlb_player_id, season)
                )
                with db.session.begin_nested():
                    hitting = groups.get("hitting")
                    if hitting:
                        self._upsert(
                            PlayerHittingStats,
                            {
                                "player_id": entry.player_id,
                                "team_id": entry.team_id,
                                "season": season,
                            },
                            self._hitting_values(hitting),
                        )
                    pitching = groups.get("pitching")
                    if pitching:
                        self._upsert(
                            PlayerPitchingStats,
                            {
                                "player_id": entry.player_id,
                                "team_id": entry.team_id,
                                "season": season,
                            },
                            self._pitching_values(pitching),
                        )
                db.session.commit()
                count += 1
            except Exception as exc:
                db.session.rollback()
                logger.error("Player stats sync failed for %s: %s", entry.player.full_name, exc)
            time.sleep(self.throttle_seconds)
        return count

    def sync_live_games(self) -> int:
        active_statuses = [
            GameStatus.LIVE.value,
            GameStatus.DELAYED.value,
            GameStatus.SUSPENDED.value,
        ]
        games = db.session.execute(
            db.select(Game).where(Game.normalized_status.in_(active_statuses))
        ).scalars().all()
        count = 0
        for game in games:
            try:
                payload = self.client.live_feed(game.game_pk)
                game_data = payload.get("gameData") or {}
                live_data = payload.get("liveData") or {}
                status = game_data.get("status") or {}
                linescore = live_data.get("linescore") or {}
                game.normalized_status = normalize_game_status(status).value
                game.abstract_status = status.get("abstractGameState")
                game.detailed_status = status.get("detailedState")
                game.current_inning = _int(linescore.get("currentInning"))
                game.inning_half = linescore.get("inningHalf") or linescore.get("inningState")
                teams = linescore.get("teams") or {}
                game.home_score = _int((teams.get("home") or {}).get("runs"))
                game.away_score = _int((teams.get("away") or {}).get("runs"))
                decisions = live_data.get("decisions") or {}
                winning_pitcher = self._upsert_person(decisions.get("winner"))
                losing_pitcher = self._upsert_person(decisions.get("loser"))
                save_pitcher = self._upsert_person(decisions.get("save"))
                game.winning_pitcher_id = winning_pitcher.id if winning_pitcher else None
                game.losing_pitcher_id = losing_pitcher.id if losing_pitcher else None
                game.save_pitcher_id = save_pitcher.id if save_pitcher else None
                decision_pitchers = {}
                if game.home_score is not None and game.away_score is not None:
                    home_won = game.home_score > game.away_score
                    winning_team = game.home_team if home_won else game.away_team
                    losing_team = game.away_team if home_won else game.home_team
                    for pitcher, team in (
                        (winning_pitcher, winning_team),
                        (losing_pitcher, losing_team),
                        (save_pitcher, winning_team),
                    ):
                        if pitcher:
                            decision_pitchers[
                                (pitcher.id, team.id, game.season)
                            ] = (pitcher.mlb_player_id, team.mlb_team_id)
                trimmed = {
                    "linescore": linescore,
                    "decisions": decisions,
                    "scoringPlays": (live_data.get("plays") or {}).get("scoringPlays", []),
                    "currentPlay": (live_data.get("plays") or {}).get("currentPlay"),
                }
                self._upsert(
                    GameSnapshot,
                    {
                        "game_pk": game.game_pk,
                        "snapshot_type": "LIVE",
                        "source_hash": _source_hash(trimmed),
                    },
                    {
                        "inning": game.current_inning,
                        "payload": trimmed,
                        "fetched_at": datetime.now(timezone.utc),
                    },
                )
                boxscore = live_data.get("boxscore") or {}
                if boxscore:
                    self._upsert(
                        GameSnapshot,
                        {
                            "game_pk": game.game_pk,
                            "snapshot_type": "BOX_SCORE",
                            "source_hash": _source_hash(boxscore),
                        },
                        {
                            "inning": game.current_inning,
                            "payload": boxscore,
                            "fetched_at": datetime.now(timezone.utc),
                        },
                    )
                db.session.commit()
                self._sync_pitcher_stats(decision_pitchers)
                count += 1
            except Exception as exc:
                db.session.rollback()
                logger.error("Live sync failed for game %s: %s", game.game_pk, exc)
        return count
