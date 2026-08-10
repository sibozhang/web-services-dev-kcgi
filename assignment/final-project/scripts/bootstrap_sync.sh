#!/bin/sh
set -eu

season="${MLB_SEASON:-2026}"
start="${MLB_SYNC_START:-${season}-03-25}"
final="${MLB_SYNC_END:-${season}-09-27}"
keep_alive="${BOOTSTRAP_KEEP_ALIVE:-1}"

echo "Starting bootstrap sync: season=${season}, window=${start}:${final}"
flask --app wsgi:app mark-bootstrap-started --season "$season"
flask --app wsgi:app sync-teams

while :; do
    end="$(date -u -d "$start +6 days" +%F)"
    if [ "$end" \> "$final" ]; then
        end="$final"
    fi
    flask --app wsgi:app sync-schedule --start "$start" --end "$end"
    if [ "$end" = "$final" ]; then
        break
    fi
    start="$(date -u -d "$end +1 day" +%F)"
done

flask --app wsgi:app sync-standings --season "$season"
flask --app wsgi:app sync-rosters --season "$season"
flask --app wsgi:app sync-team-stats --season "$season"
flask --app wsgi:app sync-player-stats --season "$season"
flask --app wsgi:app mark-bootstrap-complete --season "$season"
echo "BOOTSTRAP_COMPLETE"

if [ "$keep_alive" = "1" ]; then
    tail -f /dev/null
fi
