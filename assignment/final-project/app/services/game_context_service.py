from collections.abc import Iterable

from app.extensions import db
from app.models import Game, PlayerPitchingStats, Standing


def standings_by_team(season: int, team_ids: Iterable[int] | None = None) -> dict[int, Standing]:
    query = db.select(Standing).where(Standing.season == season)
    if team_ids is not None:
        ids = list(team_ids)
        if not ids:
            return {}
        query = query.where(Standing.team_id.in_(ids))
    rows = db.session.execute(query).scalars().all()
    return {row.team_id: row for row in rows}


def decision_pitching_stats_by_game(
    games: Iterable[Game],
) -> dict[int, dict[str, PlayerPitchingStats | None]]:
    game_list = list(games)
    player_ids = {
        player_id
        for game in game_list
        for player_id in (
            game.winning_pitcher_id,
            game.losing_pitcher_id,
            game.save_pitcher_id,
        )
        if player_id
    }
    if not player_ids:
        return {game.game_pk: {} for game in game_list}

    seasons = {game.season for game in game_list}
    rows = db.session.execute(
        db.select(PlayerPitchingStats).where(
            PlayerPitchingStats.player_id.in_(player_ids),
            PlayerPitchingStats.season.in_(seasons),
        )
    ).scalars().all()
    exact = {
        (row.player_id, row.team_id, row.season): row
        for row in rows
    }
    fallback: dict[tuple[int, int], PlayerPitchingStats] = {}
    for row in rows:
        key = (row.player_id, row.season)
        previous = fallback.get(key)
        if previous is None or row.updated_at > previous.updated_at:
            fallback[key] = row

    result: dict[int, dict[str, PlayerPitchingStats | None]] = {}
    for game in game_list:
        home_won = (
            game.home_score is not None
            and game.away_score is not None
            and game.home_score > game.away_score
        )
        winning_team_id = game.home_team_id if home_won else game.away_team_id
        losing_team_id = game.away_team_id if home_won else game.home_team_id
        role_values = (
            ("winner", game.winning_pitcher_id, winning_team_id),
            ("loser", game.losing_pitcher_id, losing_team_id),
            ("save", game.save_pitcher_id, winning_team_id),
        )
        result[game.game_pk] = {
            role: (
                exact.get((player_id, team_id, game.season))
                or fallback.get((player_id, game.season))
            )
            if player_id
            else None
            for role, player_id, team_id in role_values
        }
    return result


def probable_pitching_stats_by_game(
    games: Iterable[Game],
) -> dict[int, dict[str, PlayerPitchingStats | None]]:
    game_list = list(games)
    player_ids = {
        player_id
        for game in game_list
        for player_id in (
            game.probable_away_pitcher_id,
            game.probable_home_pitcher_id,
        )
        if player_id
    }
    if not player_ids:
        return {game.game_pk: {} for game in game_list}

    seasons = {game.season for game in game_list}
    rows = db.session.execute(
        db.select(PlayerPitchingStats).where(
            PlayerPitchingStats.player_id.in_(player_ids),
            PlayerPitchingStats.season.in_(seasons),
        )
    ).scalars().all()
    exact = {
        (row.player_id, row.team_id, row.season): row
        for row in rows
    }
    fallback: dict[tuple[int, int], PlayerPitchingStats] = {}
    for row in rows:
        key = (row.player_id, row.season)
        previous = fallback.get(key)
        if previous is None or row.updated_at > previous.updated_at:
            fallback[key] = row

    result = {}
    for game in game_list:
        result[game.game_pk] = {
            "away": (
                exact.get(
                    (
                        game.probable_away_pitcher_id,
                        game.away_team_id,
                        game.season,
                    )
                )
                or fallback.get((game.probable_away_pitcher_id, game.season))
            )
            if game.probable_away_pitcher_id
            else None,
            "home": (
                exact.get(
                    (
                        game.probable_home_pitcher_id,
                        game.home_team_id,
                        game.season,
                    )
                )
                or fallback.get((game.probable_home_pitcher_id, game.season))
            )
            if game.probable_home_pitcher_id
            else None,
        }
    return result


def recent_team_records(
    game: Game, limit: int = 10
) -> dict[str, dict[str, int]]:
    """Return each team's completed results immediately before this game."""

    def record_for(team_id: int) -> dict[str, int]:
        rows = db.session.execute(
            db.select(Game)
            .where(
                Game.season == game.season,
                Game.game_pk != game.game_pk,
                Game.normalized_status == "FINAL",
                Game.start_time_utc < game.start_time_utc,
                db.or_(Game.home_team_id == team_id, Game.away_team_id == team_id),
            )
            .order_by(Game.start_time_utc.desc())
            .limit(limit)
        ).scalars().all()
        wins = losses = ties = 0
        for row in rows:
            is_home = row.home_team_id == team_id
            team_score = row.home_score if is_home else row.away_score
            opponent_score = row.away_score if is_home else row.home_score
            if team_score is None or opponent_score is None:
                continue
            if team_score > opponent_score:
                wins += 1
            elif team_score < opponent_score:
                losses += 1
            else:
                ties += 1
        return {
            "games": wins + losses + ties,
            "wins": wins,
            "losses": losses,
            "ties": ties,
        }

    return {
        "away": record_for(game.away_team_id),
        "home": record_for(game.home_team_id),
    }
