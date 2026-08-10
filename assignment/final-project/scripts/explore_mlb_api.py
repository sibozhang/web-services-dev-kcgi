#!/usr/bin/env python3
"""手动探索 MLB Stats API，并保存体积受控的真实 JSON。

示例：
  python scripts/explore_mlb_api.py teams --output /tmp/teams.json
  python scripts/explore_mlb_api.py schedule --date 2026-07-21 --output /tmp/schedule.json
  python scripts/explore_mlb_api.py live --game-pk 822786 --output /tmp/live.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.mlb_client import MLBClient  # noqa: E402


def trim(resource: str, payload: dict) -> dict:
    if resource == "teams":
        return {
            "teams": [
                {
                    key: team.get(key)
                    for key in ("id", "name", "abbreviation", "league", "division", "venue")
                }
                for team in payload.get("teams", [])
            ]
        }
    if resource == "schedule":
        keys = {
            "gamePk",
            "gameDate",
            "officialDate",
            "season",
            "gameType",
            "status",
            "teams",
            "venue",
            "linescore",
            "decisions",
        }
        return {
            "dates": [
                {
                    "date": day.get("date"),
                    "games": [
                        {key: value for key, value in game.items() if key in keys}
                        for game in day.get("games", [])
                    ],
                }
                for day in payload.get("dates", [])
            ]
        }
    if resource == "standings":
        return {"records": payload.get("records", [])}
    if resource == "roster":
        return {"roster": payload.get("roster", [])}
    if resource in {"team-stats", "player-stats"}:
        return {"stats": payload.get("stats", [])}
    if resource == "boxscore":
        return {
            "teams": payload.get("teams"),
            "info": payload.get("info"),
            "officials": payload.get("officials"),
        }
    if resource == "live":
        live = payload.get("liveData") or {}
        return {
            "gamePk": payload.get("gamePk"),
            "gameData": {
                key: (payload.get("gameData") or {}).get(key)
                for key in ("datetime", "status", "teams", "venue")
            },
            "liveData": {
                "linescore": live.get("linescore"),
                "plays": {
                    "scoringPlays": (live.get("plays") or {}).get("scoringPlays"),
                    "currentPlay": (live.get("plays") or {}).get("currentPlay"),
                },
            },
        }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "resource",
        choices=[
            "teams",
            "schedule",
            "standings",
            "roster",
            "team-stats",
            "player-stats",
            "boxscore",
            "live",
        ],
    )
    parser.add_argument("--date")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--team-id", type=int)
    parser.add_argument("--player-id", type=int)
    parser.add_argument("--game-pk", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    client = MLBClient()
    if args.resource == "teams":
        payload = client.teams()
    elif args.resource == "schedule":
        if not args.date:
            parser.error("schedule requires --date")
        payload = client.schedule(args.date, args.date)
    elif args.resource == "standings":
        payload = client.standings(args.season)
    elif args.resource == "roster":
        if not args.team_id:
            parser.error("roster requires --team-id")
        payload = client.roster(args.team_id, args.season)
    elif args.resource == "team-stats":
        if not args.team_id:
            parser.error("team-stats requires --team-id")
        payload = client.team_stats(args.team_id, args.season)
    elif args.resource == "player-stats":
        if not args.player_id:
            parser.error("player-stats requires --player-id")
        payload = client.player_stats(args.player_id, args.season)
    elif args.resource == "boxscore":
        if not args.game_pk:
            parser.error("boxscore requires --game-pk")
        payload = client.boxscore(args.game_pk)
    else:
        if not args.game_pk:
            parser.error("live requires --game-pk")
        payload = client.live_feed(args.game_pk)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(trim(args.resource, payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved trimmed {args.resource} fixture to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
