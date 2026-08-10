from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_api_image_supports_non_migrating_sidecars():
    entrypoint = (ROOT / "entrypoint.sh").read_text()
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert 'SKIP_DB_MIGRATIONS", "0") == "1"' in entrypoint
    assert 'if [ "${SKIP_DB_MIGRATIONS:-0}" = "1" ]' in entrypoint
    assert "Skipping database migrations for sidecar process" in entrypoint
    assert "/app/scripts/*.sh" in dockerfile


def test_bootstrap_script_marks_database_ready_only_after_full_sync():
    script = (ROOT / "scripts" / "bootstrap_sync.sh").read_text()

    started = script.index("mark-bootstrap-started")
    schedule = script.index("sync-schedule")
    player_stats = script.index("sync-player-stats")
    completed = script.index("mark-bootstrap-complete")
    assert started < schedule < player_stats < completed
    assert 'echo "BOOTSTRAP_COMPLETE"' in script
    assert 'BOOTSTRAP_KEEP_ALIVE:-1' in script


def test_sync_worker_uses_requested_production_frequencies():
    script = (ROOT / "scripts" / "sync_worker.sh").read_text()

    assert "SYNC_CURRENT_INTERVAL_SECONDS:-300" in script
    assert "SYNC_DAILY_INTERVAL_SECONDS:-43200" in script
    assert "wait-for-bootstrap" in script
    assert "sync-current-games --lookback-days 1" in script
    assert "sync-standings --season" in script
    assert "sync-team-stats --season" in script
    assert "sync-rosters --season" in script
    assert "sync-player-stats --season" in script
