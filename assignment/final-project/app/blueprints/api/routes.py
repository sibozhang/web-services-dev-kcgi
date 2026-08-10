from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, current_app, jsonify, redirect, request, session
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    unset_jwt_cookies,
    verify_jwt_in_request,
)
from flask_jwt_extended.exceptions import CSRFError

from app.extensions import db, oauth
from app.models import (
    AIAnalysis,
    CalendarGameEvent,
    Game,
    GameSnapshot,
    GoogleCalendarToken,
    OAuthAccount,
    Player,
    PlayerHittingStats,
    PlayerPitchingStats,
    Roster,
    Standing,
    Team,
    TeamSeasonStats,
    User,
)
from app.services.ai_service import (
    AIRateLimitError,
    AIService,
    AIServiceError,
    PregameAnalysisUnavailable,
)
from app.services.auth_service import (
    current_user,
    issue_login_cookie,
    new_oauth_state,
    normalize_email,
    validate_oauth_state,
    validate_password,
)
from app.services.boxscore_service import normalize_boxscore
from app.services.game_context_service import (
    decision_pitching_stats_by_game,
    probable_pitching_stats_by_game,
    standings_by_team,
)
from app.services.google_calendar_service import (
    CalendarServiceError,
    GoogleCalendarService,
)
from app.services.mlb_client import MLBClient, MLBClientError
from app.services.mlb_sync_service import MLBSyncService
from app.services.time_service import jst_day_utc_range
from app.services.token_service import TokenCipher, TokenEncryptionError

from .serializers import (
    analysis_resource,
    game_resource,
    hitting_stats_resource,
    linescore_resource,
    player_pitching_resource,
    player_resource,
    roster_resource,
    standing_resource,
    team_resource,
    team_stats_resource,
)


bp = Blueprint("api", __name__, url_prefix="/api")
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def api_error(message: str, status: int, code: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except CSRFError:
            return api_error(
                "安全验证信息缺失或已过期，请刷新页面后重试。",
                401,
                "CSRF_VALIDATION_FAILED",
            )
        except Exception:
            return api_error("请先登录。", 401, "AUTHENTICATION_REQUIRED")
        return view(*args, **kwargs)

    return wrapped


def _json_body():
    return request.get_json(silent=True) or {}


def _today_jst() -> date:
    return datetime.now(timezone.utc).astimezone(
        ZoneInfo(current_app.config["APP_TIMEZONE"])
    ).date()


def _latest_snapshot(game_pk: int, snapshot_types: tuple[str, ...]):
    return db.session.execute(
        db.select(GameSnapshot)
        .where(
            GameSnapshot.game_pk == game_pk,
            GameSnapshot.snapshot_type.in_(snapshot_types),
        )
        .order_by(GameSnapshot.fetched_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _game_or_none(game_pk: int):
    return db.session.execute(
        db.select(Game).where(Game.game_pk == game_pk)
    ).scalar_one_or_none()


def _game_resources(games: list[Game]) -> list[dict]:
    if not games:
        return []
    season_ids = {game.season for game in games}
    team_ids = {
        team_id
        for game in games
        for team_id in (game.home_team_id, game.away_team_id)
    }
    standing_map = {}
    for season in season_ids:
        standing_map.update(standings_by_team(season, team_ids))
    decisions = decision_pitching_stats_by_game(games)
    probables = probable_pitching_stats_by_game(games)
    return [
        game_resource(
            game,
            standing_map,
            decisions.get(game.game_pk),
            probables.get(game.game_pk),
        )
        for game in games
    ]


def _roster_groups(entries: list[Roster], season: int) -> dict:
    player_ids = {entry.player_id for entry in entries}
    team_id = entries[0].team_id if entries else None
    hitting_by_player = {}
    pitching_by_player = {}
    if player_ids:
        hitting_by_player = {
            row.player_id: row
            for row in db.session.execute(
                db.select(PlayerHittingStats).where(
                    PlayerHittingStats.player_id.in_(player_ids),
                    PlayerHittingStats.team_id == team_id,
                    PlayerHittingStats.season == season,
                )
            ).scalars()
        }
        pitching_by_player = {
            row.player_id: row
            for row in db.session.execute(
                db.select(PlayerPitchingStats).where(
                    PlayerPitchingStats.player_id.in_(player_ids),
                    PlayerPitchingStats.team_id == team_id,
                    PlayerPitchingStats.season == season,
                )
            ).scalars()
        }
    groups = {
        "active": {"pitchers": [], "position_players": []},
        "other": {"pitchers": [], "position_players": []},
    }
    for entry in entries:
        resource = roster_resource(
            entry,
            hitting_by_player.get(entry.player_id),
            pitching_by_player.get(entry.player_id),
        )
        tier = "active" if resource["is_active_roster"] else "other"
        role = "pitchers" if resource["role"] == "pitcher" else "position_players"
        groups[tier][role].append(resource)
    for tier in groups.values():
        for rows in tier.values():
            rows.sort(key=lambda item: item["player"]["full_name"])
    groups["counts"] = {
        "active": sum(len(rows) for rows in groups["active"].values()),
        "other": sum(len(rows) for rows in groups["other"].values()),
        "total": len(entries),
    }
    return groups


def _game_active_rosters(game: Game, boxscore: dict) -> dict:
    filter_appeared = game.normalized_status in {"FINAL", "LIVE"}
    category_order = ("pitchers", "catchers", "infielders", "outfielders")
    result = {}
    for side, team in (("away", game.away_team), ("home", game.home_team)):
        entries = db.session.execute(
            db.select(Roster)
            .where(
                Roster.team_id == team.id,
                Roster.season == game.season,
                db.func.lower(Roster.roster_status) == "active",
            )
            .order_by(Roster.position, Roster.jersey_number)
        ).scalars().all()
        active = _roster_groups(entries, game.season)["active"]
        resources = active["pitchers"] + active["position_players"]
        appeared_ids = {
            row.get("player_id")
            for group in ("batters", "pitchers")
            for row in (boxscore.get(side, {}).get(group) or [])
            if row.get("player_id")
        }
        groups = {category: [] for category in category_order}
        for resource in resources:
            if filter_appeared and resource["player"]["mlb_player_id"] in appeared_ids:
                continue
            position = (resource.get("position") or "").upper()
            if position in {"P", "TWP"}:
                category = "pitchers"
            elif position == "C":
                category = "catchers"
            elif position in {"LF", "CF", "RF", "OF"}:
                category = "outfielders"
            else:
                category = "infielders"
            groups[category].append(resource)
        for rows in groups.values():
            rows.sort(key=lambda item: item["player"]["full_name"])
        result[side] = {
            "team": team_resource(team),
            "groups": groups,
            "count": sum(len(groups[category]) for category in category_order),
        }
    return result


def _player_recent_appearances(player: Player, season: int, limit: int = 10) -> dict:
    team_ids = set(
        db.session.execute(
            db.select(Roster.team_id).where(
                Roster.player_id == player.id,
                Roster.season == season,
            )
        ).scalars()
    )
    team_ids.update(
        db.session.execute(
            db.select(PlayerHittingStats.team_id).where(
                PlayerHittingStats.player_id == player.id,
                PlayerHittingStats.season == season,
            )
        ).scalars()
    )
    team_ids.update(
        db.session.execute(
            db.select(PlayerPitchingStats.team_id).where(
                PlayerPitchingStats.player_id == player.id,
                PlayerPitchingStats.season == season,
            )
        ).scalars()
    )
    query = (
        db.select(GameSnapshot, Game)
        .join(Game, Game.game_pk == GameSnapshot.game_pk)
        .where(
            GameSnapshot.snapshot_type == "BOX_SCORE",
            Game.season == season,
        )
        .order_by(Game.start_time_utc.desc(), GameSnapshot.fetched_at.desc())
    )
    if team_ids:
        query = query.where(
            db.or_(Game.home_team_id.in_(team_ids), Game.away_team_id.in_(team_ids))
        )
    hitting_rows = []
    pitching_rows = []
    appearance_games = 0
    seen_games = set()
    for snapshot, game in db.session.execute(query):
        if game.game_pk in seen_games:
            continue
        seen_games.add(game.game_pk)
        boxscore = normalize_boxscore(snapshot.payload)
        appearance = None
        for side in ("away", "home"):
            hitting = next(
                (
                    row
                    for row in (boxscore.get(side, {}).get("batters") or [])
                    if row.get("player_id") == player.mlb_player_id
                ),
                None,
            )
            pitching = next(
                (
                    row
                    for row in (boxscore.get(side, {}).get("pitchers") or [])
                    if row.get("player_id") == player.mlb_player_id
                ),
                None,
            )
            if hitting or pitching:
                team = game.away_team if side == "away" else game.home_team
                opponent = game.home_team if side == "away" else game.away_team
                appearance = {
                    "game_pk": game.game_pk,
                    "start_time_jst": game.start_time_jst.isoformat(),
                    "team": team_resource(team),
                    "opponent": team_resource(opponent),
                    "is_home": side == "home",
                }
                if hitting:
                    hitting_rows.append({**appearance, **hitting})
                if pitching:
                    pitching_rows.append({**appearance, **pitching})
                break
        if appearance:
            appearance_games += 1
            if appearance_games >= limit:
                break
    return {
        "game_count": appearance_games,
        "hitting": hitting_rows,
        "pitching": pitching_rows,
    }


@bp.get("")
@bp.get("/")
def api_index():
    return {
        "data": {
            "name": "MLB Dugout REST API",
            "version": "1.0",
            "resources": {
                "games": "/api/games",
                "manual_game_sync": "/api/sync/games",
                "standings": "/api/standings",
                "teams": "/api/teams",
                "session": "/api/auth/session",
                "health": "/api/health",
            },
        }
    }


@bp.get("/meta")
def meta():
    candidates = [
        db.session.scalar(db.select(db.func.max(model.updated_at)))
        for model in (Game, Standing, Team)
    ]
    updated = max((value for value in candidates if value), default=None)
    return {
        "data": {
            "season": current_app.config["MLB_SEASON"],
            "timezone": current_app.config["APP_TIMEZONE"],
            "last_updated": updated.isoformat() if updated else None,
        }
    }


@bp.get("/health")
def health():
    try:
        db.session.execute(db.select(1))
    except Exception:
        return api_error("数据库不可用。", 503, "DATABASE_UNAVAILABLE")
    return {"data": {"status": "ok", "database": "connected"}}


@bp.post("/sync/games")
@api_login_required
def manual_game_sync():
    today = _today_jst()
    start = today - timedelta(days=1)
    service = MLBSyncService(
        MLBClient(
            base_url=current_app.config["MLB_BASE_URL"],
            connect_timeout=current_app.config["MLB_CONNECT_TIMEOUT"],
            read_timeout=current_app.config["MLB_READ_TIMEOUT"],
        )
    )
    try:
        schedule_count = service.sync_schedule(start, today)
        live_count = service.sync_live_games()
    except MLBClientError as exc:
        db.session.rollback()
        current_app.logger.warning("Manual MLB game sync failed: %s", exc)
        return api_error(
            "无法从 MLB Stats API 更新比赛数据，请稍后重试。",
            502,
            "MLB_SYNC_FAILED",
        )

    completed_at = datetime.now(timezone.utc)
    return {
        "data": {
            "schedule_window": {
                "start": start.isoformat(),
                "end": today.isoformat(),
            },
            "games_synced": schedule_count,
            "live_games_synced": live_count,
            "completed_at": completed_at.isoformat(),
        },
        "message": "比赛数据同步完成。",
    }


@bp.get("/auth/session")
def auth_session():
    user = current_user()
    return {
        "data": {
            "authenticated": user is not None,
            "csrf_token": get_jwt().get("csrf") if user else None,
            "user": (
                {"id": user.id, "email": user.email, "role": user.role}
                if user
                else None
            ),
        }
    }


@bp.post("/auth/register")
def register():
    body = _json_body()
    email = normalize_email(body.get("email", ""))
    password = body.get("password", "")
    error = validate_password(password)
    if "@" not in email or len(email) > 320:
        error = "请输入有效的邮箱地址。"
    if db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none():
        error = "无法使用该邮箱创建账号。"
    if error:
        return api_error(error, 400, "VALIDATION_ERROR")
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    response = jsonify(
        {
            "data": {
                "user": {"id": user.id, "email": user.email, "role": user.role}
            },
            "message": "注册成功，欢迎来到 MLB Dugout。",
        }
    )
    return issue_login_cookie(response, user), 201


@bp.post("/auth/login")
def login():
    body = _json_body()
    email = normalize_email(body.get("email", ""))
    password = body.get("password", "")
    user = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()
    if not user or not user.is_active or not user.check_password(password):
        return api_error("邮箱或密码不正确。", 401, "INVALID_CREDENTIALS")
    response = jsonify(
        {
            "data": {
                "user": {"id": user.id, "email": user.email, "role": user.role}
            }
        }
    )
    return issue_login_cookie(response, user)


@bp.post("/auth/logout")
@api_login_required
def logout():
    response = jsonify({"message": "已安全退出。"})
    unset_jwt_cookies(response)
    return response


@bp.get("/auth/google")
def google_login():
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not oauth.google:
        return redirect(
            current_app.config["CLIENT_URL"]
            + "/login?message=Google%20登录尚未配置"
        )
    nonce = __import__("secrets").token_urlsafe(24)
    session["google_login_nonce"] = nonce
    redirect_uri = current_app.config["GOOGLE_LOGIN_REDIRECT_URI"] or (
        current_app.config["BASE_URL"] + "/api/auth/google/callback"
    )
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)


@bp.get("/auth/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        claims = oauth.google.parse_id_token(
            token, nonce=session.pop("google_login_nonce", None)
        )
    except Exception:
        return redirect(current_app.config["CLIENT_URL"] + "/login?oauth=failed")
    if not claims or not claims.get("email_verified") or not claims.get("sub"):
        return redirect(current_app.config["CLIENT_URL"] + "/login?oauth=failed")
    account = db.session.execute(
        db.select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_subject == claims["sub"],
        )
    ).scalar_one_or_none()
    if account:
        user = account.user
    else:
        email = normalize_email(claims.get("email", ""))
        if db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none():
            return redirect(
                current_app.config["CLIENT_URL"] + "/login?oauth=email_exists"
            )
        user = User(email=email)
        db.session.add(user)
        db.session.flush()
        db.session.add(
            OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_subject=claims["sub"],
                provider_email=email,
            )
        )
        db.session.commit()
    response = redirect(current_app.config["CLIENT_URL"] + "/")
    return issue_login_cookie(response, user)


@bp.get("/games")
def games():
    today = _today_jst()
    date_value = request.args.get("date")
    month_value = request.args.get("month")
    selected_team = request.args.get("team", type=int)
    query = db.select(Game)
    response_meta = {}
    if month_value:
        try:
            month_start = date.fromisoformat(month_value + "-01")
        except ValueError:
            return api_error("month 必须使用 YYYY-MM 格式。", 400, "INVALID_MONTH")
        month_end = date(
            month_start.year,
            month_start.month,
            monthrange(month_start.year, month_start.month)[1],
        )
        start_utc, _ = jst_day_utc_range(month_start)
        _, end_utc = jst_day_utc_range(month_end)
        response_meta["month"] = month_value
    else:
        try:
            selected_date = date.fromisoformat(date_value) if date_value else today
        except ValueError:
            return api_error("date 必须使用 YYYY-MM-DD 格式。", 400, "INVALID_DATE")
        start_utc, end_utc = jst_day_utc_range(selected_date)
        response_meta["date"] = selected_date.isoformat()
    query = query.where(
        Game.start_time_utc >= start_utc, Game.start_time_utc < end_utc
    )
    if selected_team:
        team = db.session.execute(
            db.select(Team).where(Team.mlb_team_id == selected_team)
        ).scalar_one_or_none()
        if team:
            query = query.where(
                db.or_(Game.home_team_id == team.id, Game.away_team_id == team.id)
            )
        response_meta["team"] = selected_team
    rows = db.session.execute(
        query.order_by(Game.start_time_utc)
    ).scalars().all()
    return {"data": _game_resources(rows), "meta": response_meta}


@bp.get("/games/<int:game_pk>")
@api_login_required
def game_detail(game_pk):
    game = _game_or_none(game_pk)
    if not game:
        return api_error("找不到该比赛。", 404, "GAME_NOT_FOUND")
    snapshot = _latest_snapshot(game_pk, ("LIVE", "LINESCORE"))
    boxscore_snapshot = _latest_snapshot(game_pk, ("BOX_SCORE",))
    language = "ja" if request.args.get("lang") == "ja" else "zh"
    current_analysis_type = AIService.analysis_type_for(game)
    analyses = db.session.execute(
        db.select(AIAnalysis)
        .where(
            AIAnalysis.game_pk == game_pk,
            AIAnalysis.analysis_type == current_analysis_type,
            AIAnalysis.prompt_version
            == AIService.prompt_version_for(current_analysis_type, language),
        )
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    ).scalars().all()
    standing_map = standings_by_team(
        game.season, {game.home_team_id, game.away_team_id}
    )
    decision_stats = decision_pitching_stats_by_game([game]).get(game.game_pk, {})
    probable_stats = probable_pitching_stats_by_game([game]).get(game.game_pk, {})
    user_id = int(get_jwt_identity())
    calendar_connected = db.session.execute(
        db.select(GoogleCalendarToken.id).where(
            GoogleCalendarToken.user_id == user_id
        )
    ).scalar_one_or_none()
    calendar_event = db.session.execute(
        db.select(CalendarGameEvent.id).where(
            CalendarGameEvent.user_id == user_id,
            CalendarGameEvent.game_pk == game_pk,
        )
    ).scalar_one_or_none()
    boxscore = normalize_boxscore(
        boxscore_snapshot.payload if boxscore_snapshot else None
    )
    return {
        "data": {
            "game": game_resource(
                game, standing_map, decision_stats, probable_stats
            ),
            "linescore": linescore_resource(
                snapshot.payload if snapshot else None
            ),
            "boxscore": boxscore,
            "active_rosters": _game_active_rosters(game, boxscore),
            "analyses": [analysis_resource(item) for item in analyses],
            "calendar": {
                "connected": calendar_connected is not None,
                "added": calendar_event is not None,
            },
        }
    }


@bp.get("/games/<int:game_pk>/status")
@api_login_required
def game_status(game_pk):
    game = _game_or_none(game_pk)
    if not game:
        return api_error("找不到该比赛。", 404, "GAME_NOT_FOUND")
    snapshot = _latest_snapshot(game_pk, ("LIVE", "LINESCORE"))
    boxscore_snapshot = _latest_snapshot(game_pk, ("BOX_SCORE",))
    boxscore = normalize_boxscore(
        boxscore_snapshot.payload if boxscore_snapshot else None
    )
    return {
        "data": {
            "game_pk": game.game_pk,
            "status": game.normalized_status,
            "detailed_status": game.detailed_status,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "current_inning": game.current_inning,
            "inning_half": game.inning_half,
            "updated_at": game.updated_at.isoformat(),
            "linescore": linescore_resource(
                snapshot.payload if snapshot else None
            ),
            "boxscore": boxscore,
            "active_rosters": _game_active_rosters(game, boxscore),
        }
    }


@bp.post("/games/<int:game_pk>/analyses")
@api_login_required
def create_analysis(game_pk):
    game = _game_or_none(game_pk)
    if not game:
        return api_error("找不到该比赛。", 404, "GAME_NOT_FOUND")
    linescore_snapshot = _latest_snapshot(game_pk, ("LIVE", "LINESCORE"))
    boxscore_snapshot = _latest_snapshot(game_pk, ("BOX_SCORE",))
    language = "ja" if _json_body().get("language") == "ja" else "zh"
    structured_game_details = {
        "linescore": linescore_resource(
            linescore_snapshot.payload if linescore_snapshot else None
        ),
        "boxscore": normalize_boxscore(
            boxscore_snapshot.payload if boxscore_snapshot else None
        ),
    }
    service = AIService(
        api_key=current_app.config["GEMINI_API_KEY"],
        model_name=current_app.config["GEMINI_MODEL"],
    )
    try:
        analysis, cached = service.analyze_game(
            game, structured_game_details, language=language
        )
    except AIRateLimitError as exc:
        return jsonify(
            {
                "error": {
                    "code": "AI_RATE_LIMITED",
                    "message": str(exc),
                    "retry_after": exc.retry_after,
                }
            }
        ), 429
    except PregameAnalysisUnavailable as exc:
        return api_error(str(exc), 409, "PROBABLE_PITCHERS_REQUIRED")
    except AIServiceError as exc:
        return api_error(str(exc), 503, "AI_UNAVAILABLE")
    return {
        "data": analysis_resource(analysis),
        "meta": {"cached": cached},
    }, (200 if cached else 201)


@bp.get("/standings")
def standings():
    season = request.args.get(
        "season", current_app.config["MLB_SEASON"], type=int
    )
    rows = db.session.execute(
        db.select(Standing)
        .join(Standing.team)
        .where(Standing.season == season)
        .order_by(Team.division, Standing.division_rank)
    ).scalars().all()
    divisions = {}
    for row in rows:
        divisions.setdefault(row.team.division, []).append(
            {
                "team": team_resource(row.team),
                "standing": standing_resource(row),
            }
        )
    return {"data": {"season": season, "divisions": divisions}}


@bp.get("/teams")
def teams():
    rows = db.session.execute(
        db.select(Team).order_by(Team.league, Team.division, Team.name)
    ).scalars().all()
    return {"data": [team_resource(team) for team in rows]}


@bp.get("/teams/<int:mlb_team_id>")
@api_login_required
def team_detail(mlb_team_id):
    team = db.session.execute(
        db.select(Team).where(Team.mlb_team_id == mlb_team_id)
    ).scalar_one_or_none()
    if not team:
        return api_error("找不到该球队。", 404, "TEAM_NOT_FOUND")
    season = current_app.config["MLB_SEASON"]
    standing = db.session.execute(
        db.select(Standing).where(
            Standing.team_id == team.id, Standing.season == season
        )
    ).scalar_one_or_none()
    stats = db.session.execute(
        db.select(TeamSeasonStats).where(
            TeamSeasonStats.team_id == team.id,
            TeamSeasonStats.season == season,
        )
    ).scalar_one_or_none()
    roster = db.session.execute(
        db.select(Roster)
        .where(Roster.team_id == team.id, Roster.season == season)
        .order_by(Roster.position, Roster.jersey_number)
    ).scalars().all()
    today = _today_jst()
    window_start = today - timedelta(days=3)
    window_end = today + timedelta(days=3)
    start_utc, _ = jst_day_utc_range(window_start)
    _, end_utc = jst_day_utc_range(window_end)
    game_rows = db.session.execute(
        db.select(Game)
        .where(
            db.or_(Game.home_team_id == team.id, Game.away_team_id == team.id),
            Game.start_time_utc >= start_utc,
            Game.start_time_utc < end_utc,
        )
        .order_by(Game.start_time_utc)
    ).scalars().all()
    return {
        "data": {
            "team": team_resource(team),
            "standing": standing_resource(standing),
            "season_stats": team_stats_resource(stats),
            "roster": _roster_groups(roster, season),
            "game_window": {
                "start_date": window_start.isoformat(),
                "today": today.isoformat(),
                "end_date": window_end.isoformat(),
            },
            "games": _game_resources(game_rows),
        }
    }


@bp.get("/teams/<int:mlb_team_id>/schedule")
@api_login_required
def team_month_schedule(mlb_team_id):
    team = db.session.execute(
        db.select(Team).where(Team.mlb_team_id == mlb_team_id)
    ).scalar_one_or_none()
    if not team:
        return api_error("找不到该球队。", 404, "TEAM_NOT_FOUND")
    month_value = request.args.get("month") or _today_jst().strftime("%Y-%m")
    try:
        selected_month = datetime.strptime(month_value, "%Y-%m").date()
    except ValueError:
        return api_error("month 必须使用 YYYY-MM 格式。", 400, "INVALID_MONTH")
    month_start = selected_month.replace(day=1)
    month_end = selected_month.replace(
        day=monthrange(selected_month.year, selected_month.month)[1]
    )
    start_utc, _ = jst_day_utc_range(month_start)
    _, end_utc = jst_day_utc_range(month_end)
    rows = db.session.execute(
        db.select(Game)
        .where(
            db.or_(Game.home_team_id == team.id, Game.away_team_id == team.id),
            Game.start_time_utc >= start_utc,
            Game.start_time_utc < end_utc,
        )
        .order_by(Game.start_time_utc)
    ).scalars().all()
    return {
        "data": {
            "team": team_resource(team),
            "month": month_start.strftime("%Y-%m"),
            "start_date": month_start.isoformat(),
            "end_date": month_end.isoformat(),
            "today": _today_jst().isoformat(),
            "games": _game_resources(rows),
        }
    }


@bp.get("/teams/<int:mlb_team_id>/roster")
def team_roster(mlb_team_id):
    team = db.session.execute(
        db.select(Team).where(Team.mlb_team_id == mlb_team_id)
    ).scalar_one_or_none()
    if not team:
        return api_error("找不到该球队。", 404, "TEAM_NOT_FOUND")
    season = request.args.get(
        "season", current_app.config["MLB_SEASON"], type=int
    )
    rows = db.session.execute(
        db.select(Roster)
        .where(Roster.team_id == team.id, Roster.season == season)
        .order_by(Roster.position, Roster.jersey_number)
    ).scalars().all()
    return {
        "data": {
            "team": team_resource(team),
            "season": season,
            "roster": _roster_groups(rows, season),
        }
    }


@bp.get("/players/<int:mlb_player_id>")
@api_login_required
def player_detail(mlb_player_id):
    player = db.session.execute(
        db.select(Player).where(Player.mlb_player_id == mlb_player_id)
    ).scalar_one_or_none()
    if not player:
        return api_error("找不到该球员。", 404, "PLAYER_NOT_FOUND")
    season = current_app.config["MLB_SEASON"]
    language = "ja" if request.args.get("lang") == "ja" else "zh"
    hitting = db.session.execute(
        db.select(PlayerHittingStats).where(
            PlayerHittingStats.player_id == player.id,
            PlayerHittingStats.season == season,
        )
    ).scalars().all()
    pitching = db.session.execute(
        db.select(PlayerPitchingStats).where(
            PlayerPitchingStats.player_id == player.id,
            PlayerPitchingStats.season == season,
        )
    ).scalars().all()
    recent_appearances = _player_recent_appearances(player, season)
    analyses = db.session.execute(
        db.select(AIAnalysis)
        .where(
            AIAnalysis.player_id == player.id,
            AIAnalysis.analysis_type == "PLAYER",
            AIAnalysis.prompt_version
            == AIService.prompt_version_for("PLAYER", language),
        )
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    ).scalars().all()
    return {
        "data": {
            "player": player_resource(player),
            "season": season,
            "hitting": [hitting_stats_resource(row) for row in hitting],
            "pitching": [player_pitching_resource(row) for row in pitching],
            "recent_appearances": recent_appearances,
            "analyses": [analysis_resource(item) for item in analyses],
        }
    }


@bp.post("/players/<int:mlb_player_id>/analyses")
@api_login_required
def create_player_analysis(mlb_player_id):
    player = db.session.execute(
        db.select(Player).where(Player.mlb_player_id == mlb_player_id)
    ).scalar_one_or_none()
    if not player:
        return api_error("找不到该球员。", 404, "PLAYER_NOT_FOUND")
    season = current_app.config["MLB_SEASON"]
    language = "ja" if _json_body().get("language") == "ja" else "zh"
    hitting = db.session.execute(
        db.select(PlayerHittingStats).where(
            PlayerHittingStats.player_id == player.id,
            PlayerHittingStats.season == season,
        )
    ).scalars().all()
    pitching = db.session.execute(
        db.select(PlayerPitchingStats).where(
            PlayerPitchingStats.player_id == player.id,
            PlayerPitchingStats.season == season,
        )
    ).scalars().all()
    source = {
        "player": player_resource(player),
        "season": season,
        "hitting": [hitting_stats_resource(row) for row in hitting],
        "pitching": [player_pitching_resource(row) for row in pitching],
        "recent_appearances": _player_recent_appearances(player, season),
    }
    service = AIService(
        api_key=current_app.config["GEMINI_API_KEY"],
        model_name=current_app.config["GEMINI_MODEL"],
    )
    try:
        analysis, cached = service.analyze_player(
            player, source, language=language
        )
    except AIRateLimitError as exc:
        return jsonify(
            {
                "error": {
                    "code": "AI_RATE_LIMITED",
                    "message": str(exc),
                    "retry_after": exc.retry_after,
                }
            }
        ), 429
    except AIServiceError as exc:
        return api_error(str(exc), 503, "AI_UNAVAILABLE")
    return {
        "data": analysis_resource(analysis),
        "meta": {"cached": cached},
    }, (200 if cached else 201)


def _calendar_service():
    return GoogleCalendarService(
        current_app.config["GOOGLE_CLIENT_ID"],
        current_app.config["GOOGLE_CLIENT_SECRET"],
        TokenCipher(current_app.config["TOKEN_ENCRYPTION_KEY"]),
        current_app.config["CLIENT_URL"],
    )


@bp.post("/calendar/authorization")
@api_login_required
def calendar_authorization():
    if not current_app.config["GOOGLE_CLIENT_ID"]:
        return api_error(
            "Google Calendar 尚未配置。", 503, "CALENDAR_NOT_CONFIGURED"
        )
    state = new_oauth_state()
    session["calendar_oauth_state"] = state
    redirect_uri = current_app.config["GOOGLE_CALENDAR_REDIRECT_URI"] or (
        current_app.config["BASE_URL"] + "/api/calendar/callback"
    )
    params = {
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": CALENDAR_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return {
        "data": {
            "authorization_url": (
                "https://accounts.google.com/o/oauth2/v2/auth?"
                + urlencode(params)
            )
        }
    }


@bp.get("/calendar/callback")
@api_login_required
def calendar_callback():
    expected = session.pop("calendar_oauth_state", None)
    client_url = current_app.config["CLIENT_URL"]
    if not validate_oauth_state(expected, request.args.get("state")):
        return redirect(client_url + "/?calendar=state_failed")
    redirect_uri = current_app.config["GOOGLE_CALENDAR_REDIRECT_URI"] or (
        current_app.config["BASE_URL"] + "/api/calendar/callback"
    )
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": request.args.get("code"),
                "client_id": current_app.config["GOOGLE_CLIENT_ID"],
                "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=(3.05, 15),
        )
        response.raise_for_status()
        payload = response.json()
        cipher = TokenCipher(current_app.config["TOKEN_ENCRYPTION_KEY"])
        user_id = int(get_jwt_identity())
        token = db.session.execute(
            db.select(GoogleCalendarToken).where(
                GoogleCalendarToken.user_id == user_id
            )
        ).scalar_one_or_none()
        old_refresh = token.encrypted_refresh_token if token else None
        if token is None:
            token = GoogleCalendarToken(user_id=user_id)
            db.session.add(token)
        token.encrypted_access_token = cipher.encrypt(payload["access_token"])
        token.encrypted_refresh_token = (
            cipher.encrypt(payload.get("refresh_token")) or old_refresh
        )
        token.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(payload.get("expires_in", 3600))
        )
        token.scopes = payload.get("scope", CALENDAR_SCOPE)
        db.session.commit()
    except (
        requests.RequestException,
        KeyError,
        ValueError,
        TokenEncryptionError,
    ):
        db.session.rollback()
        return redirect(client_url + "/?calendar=failed")
    return redirect(client_url + "/?calendar=connected")


@bp.post("/calendar/events")
@api_login_required
def add_calendar_event():
    game_pk = (_json_body()).get("game_pk")
    try:
        game_pk = int(game_pk)
    except (TypeError, ValueError):
        return api_error("game_pk 无效。", 400, "INVALID_GAME_PK")
    game = _game_or_none(game_pk)
    if not game:
        return api_error("找不到该比赛。", 404, "GAME_NOT_FOUND")
    try:
        event, duplicate = _calendar_service().add_game(
            int(get_jwt_identity()), game
        )
    except (CalendarServiceError, TokenEncryptionError) as exc:
        return api_error(str(exc), 409, "CALENDAR_ERROR")
    return {
        "data": {
            "google_event_id": event.google_event_id,
            "game_pk": event.game_pk,
        },
        "meta": {"duplicate": duplicate},
    }, (200 if duplicate else 201)
