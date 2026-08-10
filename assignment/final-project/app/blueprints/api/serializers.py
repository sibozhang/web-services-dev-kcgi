from datetime import timezone
from decimal import Decimal

from app.models import (
    AIAnalysis,
    Game,
    Player,
    PlayerHittingStats,
    PlayerPitchingStats,
    Roster,
    Standing,
    Team,
    TeamSeasonStats,
)
from app.services.time_service import to_jst


def number(value):
    if isinstance(value, Decimal):
        return str(value)
    return value


def aware_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def team_resource(team: Team) -> dict:
    return {
        "mlb_team_id": team.mlb_team_id,
        "name": team.name,
        "abbreviation": team.abbreviation,
        "league": team.league,
        "division": team.division,
        "logo_url": team.logo_url,
        "venue_name": team.venue_name,
    }


def standing_resource(standing: Standing | None) -> dict | None:
    if standing is None:
        return None
    return {
        "wins": standing.wins,
        "losses": standing.losses,
        "winning_percentage": number(standing.winning_percentage),
        "games_back": standing.games_back,
        "division_rank": standing.division_rank,
        "league_rank": standing.league_rank,
        "home": {"wins": standing.home_wins, "losses": standing.home_losses},
        "away": {"wins": standing.away_wins, "losses": standing.away_losses},
        "last_ten": {
            "wins": standing.last_ten_wins,
            "losses": standing.last_ten_losses,
        },
        "streak": standing.streak,
        "runs_scored": standing.runs_scored,
        "runs_allowed": standing.runs_allowed,
        "run_differential": standing.run_differential,
    }


def team_stats_resource(stats: TeamSeasonStats | None) -> dict | None:
    if stats is None:
        return None
    return {
        "games_played": stats.games_played,
        "batting_avg": number(stats.batting_avg),
        "obp": number(stats.obp),
        "slg": number(stats.slg),
        "ops": number(stats.ops),
        "runs": stats.runs,
        "hits": stats.hits,
        "home_runs": stats.home_runs,
        "batting_strikeouts": stats.batting_strikeouts,
        "batting_walks": stats.batting_walks,
        "era": number(stats.era),
        "whip": number(stats.whip),
        "wins": stats.wins,
        "losses": stats.losses,
        "saves": stats.saves,
        "pitching_strikeouts": stats.pitching_strikeouts,
        "pitching_walks": stats.pitching_walks,
        "home_runs_allowed": stats.home_runs_allowed,
    }


def player_resource(player: Player) -> dict:
    return {
        "mlb_player_id": player.mlb_player_id,
        "full_name": player.full_name,
        "primary_position": player.primary_position,
        "bat_side": player.bat_side,
        "pitch_hand": player.pitch_hand,
        "birth_date": player.birth_date.isoformat() if player.birth_date else None,
        "active": player.active,
    }


def pitching_stats_resource(stats: PlayerPitchingStats | None) -> dict | None:
    if stats is None:
        return None
    return {
        "games_played": stats.games_played,
        "games_started": stats.games_started,
        "wins": stats.wins,
        "losses": stats.losses,
        "saves": stats.saves,
        "innings_pitched": (
            stats.innings_pitched if stats.innings_outs is not None else None
        ),
        "hits": stats.hits,
        "earned_runs": stats.earned_runs,
        "home_runs": stats.home_runs,
        "walks": stats.walks,
        "strikeouts": stats.strikeouts,
        "era": number(stats.era),
        "whip": number(stats.whip),
    }


def hitting_stats_resource(stats: PlayerHittingStats) -> dict:
    return {
        "team": team_resource(stats.team),
        "games_played": stats.games_played,
        "plate_appearances": stats.plate_appearances,
        "at_bats": stats.at_bats,
        "runs": stats.runs,
        "hits": stats.hits,
        "doubles": stats.doubles,
        "triples": stats.triples,
        "home_runs": stats.home_runs,
        "rbi": stats.rbi,
        "walks": stats.walks,
        "strikeouts": stats.strikeouts,
        "stolen_bases": stats.stolen_bases,
        "avg": number(stats.avg),
        "obp": number(stats.obp),
        "slg": number(stats.slg),
        "ops": number(stats.ops),
    }


def player_pitching_resource(stats: PlayerPitchingStats) -> dict:
    resource = pitching_stats_resource(stats) or {}
    resource["team"] = team_resource(stats.team)
    return resource


def roster_resource(
    entry: Roster,
    hitting: PlayerHittingStats | None = None,
    pitching: PlayerPitchingStats | None = None,
) -> dict:
    is_pitcher = entry.position in {"P", "TWP"}
    is_two_way = entry.position == "TWP"
    if is_pitcher:
        season_stats = {
            "era": number(pitching.era) if pitching else None,
            "innings_pitched": pitching.innings_pitched if pitching else None,
        }
        if is_two_way:
            season_stats.update(
                {
                    "avg": number(hitting.avg) if hitting else None,
                    "hits": hitting.hits if hitting else None,
                    "at_bats": hitting.at_bats if hitting else None,
                    "rbi": hitting.rbi if hitting else None,
                    "ops": number(hitting.ops) if hitting else None,
                }
            )
    else:
        season_stats = {
            "avg": number(hitting.avg) if hitting else None,
            "hits": hitting.hits if hitting else None,
            "at_bats": hitting.at_bats if hitting else None,
            "rbi": hitting.rbi if hitting else None,
            "ops": number(hitting.ops) if hitting else None,
        }
    return {
        "jersey_number": entry.jersey_number,
        "position": entry.position,
        "roster_status": entry.roster_status,
        "is_active_roster": (entry.roster_status or "").lower() == "active",
        "is_two_way": is_two_way,
        "role": "pitcher" if is_pitcher else "position_player",
        "season_stats": season_stats,
        "player": player_resource(entry.player),
    }


def _decision_resource(code: str, pitcher, stats) -> dict | None:
    if pitcher is None:
        return None
    return {
        "code": code,
        "pitcher": player_resource(pitcher),
        "season_stats": pitching_stats_resource(stats),
    }


def _probable_pitcher_resource(pitcher, stats) -> dict | None:
    if pitcher is None:
        return None
    resource = player_resource(pitcher)
    resource["season_stats"] = pitching_stats_resource(stats)
    return resource


def game_resource(
    game: Game,
    standings: dict[int, Standing] | None = None,
    decision_stats: dict[str, PlayerPitchingStats | None] | None = None,
    probable_stats: dict[str, PlayerPitchingStats | None] | None = None,
) -> dict:
    standings = standings or {}
    decision_stats = decision_stats or {}
    probable_stats = probable_stats or {}
    decisions = [
        _decision_resource(
            "W", game.winning_pitcher, decision_stats.get("winner")
        ),
        _decision_resource(
            "L", game.losing_pitcher, decision_stats.get("loser")
        ),
        _decision_resource("S", game.save_pitcher, decision_stats.get("save")),
    ]
    return {
        "game_pk": game.game_pk,
        "season": game.season,
        "game_type": game.game_type,
        "official_date": game.official_date.isoformat(),
        "start_time_utc": aware_utc(game.start_time_utc).isoformat(),
        "start_time_jst": to_jst(aware_utc(game.start_time_utc)).isoformat(),
        "venue_name": game.venue_name,
        "status": {
            "normalized": game.normalized_status,
            "abstract": game.abstract_status,
            "detailed": game.detailed_status,
            "current_inning": game.current_inning,
            "inning_half": game.inning_half,
        },
        "away": {
            "team": team_resource(game.away_team),
            "score": game.away_score,
            "standing": standing_resource(standings.get(game.away_team_id)),
            "probable_pitcher": _probable_pitcher_resource(
                game.probable_away_pitcher, probable_stats.get("away")
            ),
        },
        "home": {
            "team": team_resource(game.home_team),
            "score": game.home_score,
            "standing": standing_resource(standings.get(game.home_team_id)),
            "probable_pitcher": _probable_pitcher_resource(
                game.probable_home_pitcher, probable_stats.get("home")
            ),
        },
        "decisions": [decision for decision in decisions if decision],
        "updated_at": game.updated_at.isoformat(),
    }


def linescore_resource(payload: dict | None) -> dict | None:
    if not payload:
        return None
    raw = payload.get("linescore", payload)
    innings = []
    for inning in raw.get("innings") or []:
        innings.append(
            {
                "number": inning.get("num"),
                "away": {
                    key: (inning.get("away") or {}).get(key)
                    for key in ("runs", "hits", "errors")
                },
                "home": {
                    key: (inning.get("home") or {}).get(key)
                    for key in ("runs", "hits", "errors")
                },
            }
        )
    teams = raw.get("teams") or {}
    return {
        "innings": innings,
        "totals": {
            side: {
                key: (teams.get(side) or {}).get(key)
                for key in ("runs", "hits", "errors")
            }
            for side in ("away", "home")
        },
    }


def analysis_resource(analysis: AIAnalysis) -> dict:
    return {
        "id": analysis.id,
        "analysis_type": analysis.analysis_type,
        "model_name": analysis.model_name,
        "content": analysis.content,
        "created_at": analysis.created_at.isoformat(),
    }
