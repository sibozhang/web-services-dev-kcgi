from datetime import date, datetime, timedelta, timezone
import time
from zoneinfo import ZoneInfo

import click
from flask import current_app

from app.extensions import db
from app.models import ApiResponse
from app.services.mlb_client import MLBClient, MLBClientError
from app.services.mlb_sync_service import MLBSyncService


def _bootstrap_marker_key(season: int) -> str:
    return f"internal:bootstrap:{season}"


def _set_bootstrap_state(season: int, state: str) -> None:
    now = datetime.now(timezone.utc)
    marker = db.session.execute(
        db.select(ApiResponse).where(
            ApiResponse.cache_key == _bootstrap_marker_key(season)
        )
    ).scalar_one_or_none()
    values = {
        "endpoint": "internal://bootstrap",
        "params_hash": "0" * 64,
        "payload": {
            "season": season,
            "state": state,
            "updated_at": now.isoformat(),
        },
        "fetched_at": now,
        "expires_at": now + timedelta(days=3660),
    }
    if marker is None:
        marker = ApiResponse(
            cache_key=_bootstrap_marker_key(season),
            **values,
        )
        db.session.add(marker)
    else:
        for key, value in values.items():
            setattr(marker, key, value)
    db.session.commit()


def _service() -> MLBSyncService:
    return MLBSyncService(
        MLBClient(
            base_url=current_app.config["MLB_BASE_URL"],
            connect_timeout=current_app.config["MLB_CONNECT_TIMEOUT"],
            read_timeout=current_app.config["MLB_READ_TIMEOUT"],
        )
    )


def _run(action, label: str):
    try:
        result = action()
    except MLBClientError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{label}: {result}")


def register_commands(app):
    @app.cli.command("mark-bootstrap-started")
    @click.option("--season", required=True, type=int)
    def mark_bootstrap_started(season):
        """记录全量初始化已经开始，自动同步 worker 将继续等待。"""
        _set_bootstrap_state(season, "started")
        click.echo(f"bootstrap state: started, season={season}")

    @app.cli.command("mark-bootstrap-complete")
    @click.option("--season", required=True, type=int)
    def mark_bootstrap_complete(season):
        """记录全量初始化完成，允许自动同步 worker 启动。"""
        _set_bootstrap_state(season, "complete")
        click.echo(f"bootstrap state: complete, season={season}")

    @app.cli.command("wait-for-bootstrap")
    @click.option("--season", required=True, type=int)
    @click.option(
        "--poll-seconds",
        default=30,
        show_default=True,
        type=click.IntRange(min=1),
    )
    @click.option(
        "--timeout-seconds",
        default=0,
        show_default=True,
        type=click.IntRange(min=0),
        help="0 表示一直等待。",
    )
    def wait_for_bootstrap(season, poll_seconds, timeout_seconds):
        """等待全量初始化完成标记。"""
        started_at = time.monotonic()
        key = _bootstrap_marker_key(season)
        while True:
            marker = db.session.execute(
                db.select(ApiResponse).where(ApiResponse.cache_key == key)
            ).scalar_one_or_none()
            if marker and marker.payload.get("state") == "complete":
                click.echo(f"bootstrap ready: season={season}")
                return
            if timeout_seconds and time.monotonic() - started_at >= timeout_seconds:
                raise click.ClickException(
                    f"bootstrap marker was not ready within {timeout_seconds} seconds"
                )
            click.echo(f"waiting for bootstrap: season={season}")
            db.session.expire_all()
            time.sleep(poll_seconds)

    @app.cli.command("sync-teams")
    def sync_teams():
        """同步 30 支 MLB 球队。"""
        _run(_service().sync_teams, "teams")

    @app.cli.command("sync-schedule")
    @click.option("--start", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
    @click.option("--end", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
    def sync_schedule(start, end):
        """同步指定日期范围的赛程。"""
        if end.date() < start.date():
            raise click.ClickException("--end 不能早于 --start")
        _run(lambda: _service().sync_schedule(start.date(), end.date()), "games")

    @app.cli.command("sync-standings")
    @click.option("--season", required=True, type=int)
    def sync_standings(season):
        """同步常规赛排名。"""
        _run(lambda: _service().sync_standings(season), "standings")

    @app.cli.command("sync-rosters")
    @click.option("--season", required=True, type=int)
    def sync_rosters(season):
        """同步 active/40Man roster 与球员赛季统计。"""
        _run(lambda: _service().sync_rosters(season), "rosters")

    @app.cli.command("sync-team-stats")
    @click.option("--season", required=True, type=int)
    def sync_team_stats(season):
        """同步球队赛季统计。"""
        _run(lambda: _service().sync_team_stats(season), "team stats")

    @app.cli.command("sync-player-stats")
    @click.option("--season", required=True, type=int)
    def sync_player_stats(season):
        """同步 roster 球员的赛季统计。"""
        _run(lambda: _service().sync_player_stats(season), "player stats")

    @app.cli.command("sync-live-games")
    def sync_live_games():
        """同步数据库中正在进行或中断的比赛。"""
        _run(_service().sync_live_games, "live games")

    @app.cli.command("sync-current-games")
    @click.option(
        "--lookback-days",
        default=1,
        show_default=True,
        type=click.IntRange(min=0, max=7),
    )
    def sync_current_games(lookback_days):
        """刷新当前 JST 日期附近的赛程，并同步进行中比赛详情。"""
        today = datetime.now(timezone.utc).astimezone(
            ZoneInfo(current_app.config["APP_TIMEZONE"])
        ).date()
        start = today - timedelta(days=lookback_days)
        service = _service()
        try:
            schedule_count = service.sync_schedule(start, today)
            live_count = service.sync_live_games()
        except MLBClientError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(
            f"current games: schedule={schedule_count}, live={live_count}, "
            f"window={start}:{today}"
        )

    @app.cli.command("sync-all")
    @click.option("--season", required=True, type=int)
    def sync_all(season):
        """按依赖顺序执行完整初始同步。"""
        service = _service()
        click.echo(f"Starting MLB sync for season {season}")
        click.echo(f"teams: {service.sync_teams()}")
        click.echo(
            "games: "
            f"{service.sync_schedule(date(season, 1, 1), date(season, 12, 31))}"
        )
        click.echo(f"standings: {service.sync_standings(season)}")
        click.echo(f"rosters: {service.sync_rosters(season)}")
        click.echo(f"team stats: {service.sync_team_stats(season)}")
        click.echo("Sync complete")
