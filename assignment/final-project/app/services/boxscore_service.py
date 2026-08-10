from typing import Any


def _player(team_payload: dict, player_id: int) -> dict:
    players = team_payload.get("players") or {}
    return players.get(f"ID{player_id}") or players.get(str(player_id)) or {}


def _ordered_player_ids(team_payload: dict, group: str) -> list[int]:
    listed = team_payload.get(group) or []
    if listed:
        return [int(player_id) for player_id in listed]

    players = team_payload.get("players") or {}
    rows = []
    for raw in players.values():
        player_id = (raw.get("person") or {}).get("id")
        if not player_id:
            continue
        if group == "batters":
            order = raw.get("battingOrder") or "9999"
        else:
            order = "0" if (raw.get("stats") or {}).get("pitching") else "9999"
        rows.append((str(order).zfill(4), int(player_id)))
    return [player_id for _order, player_id in sorted(rows)]


def _batting_rows(team_payload: dict) -> list[dict[str, Any]]:
    rows = []
    for player_id in _ordered_player_ids(team_payload, "batters"):
        raw = _player(team_payload, player_id)
        batting = (raw.get("stats") or {}).get("batting") or {}
        if not batting or not batting.get("gamesPlayed"):
            continue
        season = (raw.get("seasonStats") or {}).get("batting") or {}
        person = raw.get("person") or {}
        rows.append(
            {
                "player_id": player_id,
                "position": (raw.get("position") or {}).get("abbreviation") or "—",
                "name": person.get("boxscoreName") or person.get("fullName") or "—",
                "at_bats": batting.get("atBats", 0),
                "runs": batting.get("runs", 0),
                "hits": batting.get("hits", 0),
                "home_runs": batting.get("homeRuns", 0),
                "rbi": batting.get("rbi", 0),
                "walks": batting.get("baseOnBalls", 0),
                "strikeouts": batting.get("strikeOuts", 0),
                "avg": season.get("avg", "—"),
                "ops": season.get("ops", "—"),
            }
        )
    return rows


def _pitching_rows(team_payload: dict) -> list[dict[str, Any]]:
    rows = []
    for appearance_index, player_id in enumerate(
        _ordered_player_ids(team_payload, "pitchers")
    ):
        raw = _player(team_payload, player_id)
        pitching = (raw.get("stats") or {}).get("pitching") or {}
        if not pitching or pitching.get("inningsPitched") is None:
            continue
        season = (raw.get("seasonStats") or {}).get("pitching") or {}
        person = raw.get("person") or {}
        rows.append(
            {
                "player_id": player_id,
                "name": person.get("boxscoreName") or person.get("fullName") or "—",
                "role": "starter" if appearance_index == 0 else "reliever",
                "innings": pitching.get("inningsPitched", "—"),
                "hits": pitching.get("hits", 0),
                "runs": pitching.get("runs", 0),
                "earned_runs": pitching.get("earnedRuns", 0),
                "walks": pitching.get("baseOnBalls", 0),
                "strikeouts": pitching.get("strikeOuts", 0),
                "home_runs": pitching.get("homeRuns", 0),
                "era": season.get("era", "—"),
                "note": pitching.get("note"),
            }
        )
    return rows


def _bullpen_rows(team_payload: dict) -> list[dict[str, Any]]:
    appeared = set(team_payload.get("pitchers") or [])
    rows = []
    for player_id in team_payload.get("bullpen") or []:
        if player_id in appeared:
            continue
        raw = _player(team_payload, int(player_id))
        season = (raw.get("seasonStats") or {}).get("pitching") or {}
        if not season:
            continue
        person = raw.get("person") or {}
        status = raw.get("gameStatus") or {}
        rows.append(
            {
                "name": person.get("boxscoreName") or person.get("fullName") or "—",
                "games": season.get("gamesPlayed"),
                "innings": season.get("inningsPitched"),
                "era": season.get("era"),
                "whip": season.get("whip"),
                "saves": season.get("saves"),
                "holds": season.get("holds"),
                "blown_saves": season.get("blownSaves"),
                "strikeouts": season.get("strikeOuts"),
                "walks": season.get("baseOnBalls"),
                "listed_in_bullpen": bool(status.get("isOnBench", True)),
            }
        )
    return rows


def normalize_boxscore(payload: dict | None) -> dict[str, dict]:
    teams = (payload or {}).get("teams") or {}
    result = {}
    for side in ("away", "home"):
        team_payload = teams.get(side) or {}
        team = team_payload.get("team") or {}
        team_stats = team_payload.get("teamStats") or {}
        result[side] = {
            "team_name": team.get("name"),
            "batters": _batting_rows(team_payload),
            "pitchers": _pitching_rows(team_payload),
            "bullpen": _bullpen_rows(team_payload),
            "batting_totals": team_stats.get("batting") or {},
            "pitching_totals": team_stats.get("pitching") or {},
        }
    if not any(
        result[side]["batters"] or result[side]["pitchers"]
        for side in ("away", "home")
    ):
        return {}
    return result
