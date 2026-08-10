#!/bin/sh
set -eu

season="${MLB_SEASON:-2026}"
current_interval="${SYNC_CURRENT_INTERVAL_SECONDS:-300}"
daily_interval="${SYNC_DAILY_INTERVAL_SECONDS:-43200}"
poll_interval="${SYNC_WORKER_POLL_SECONDS:-30}"
startup_grace="${SYNC_WORKER_STARTUP_GRACE_SECONDS:-60}"
max_cycles="${SYNC_WORKER_MAX_CYCLES:-0}"

echo "Sync worker starting: current=${current_interval}s, daily=${daily_interval}s"
sleep "$startup_grace"
flask --app wsgi:app wait-for-bootstrap \
    --season "$season" \
    --poll-seconds "$poll_interval"

now="$(date +%s)"
next_current=0
next_daily=$((now + daily_interval))
cycles=0

while :; do
    now="$(date +%s)"

    if [ "$now" -ge "$next_current" ]; then
        flask --app wsgi:app sync-current-games --lookback-days 1 || true
        next_current=$((now + current_interval))
    fi

    if [ "$now" -ge "$next_daily" ]; then
        flask --app wsgi:app sync-standings --season "$season" || true
        flask --app wsgi:app sync-team-stats --season "$season" || true
        flask --app wsgi:app sync-rosters --season "$season" || true
        flask --app wsgi:app sync-player-stats --season "$season" || true
        next_daily=$((now + daily_interval))
    fi

    cycles=$((cycles + 1))
    if [ "$max_cycles" -gt 0 ] && [ "$cycles" -ge "$max_cycles" ]; then
        echo "Sync worker stopped after ${cycles} test cycle(s)"
        break
    fi
    sleep "$poll_interval"
done
