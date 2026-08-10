from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_client_is_static_vanilla_javascript_without_template_syntax():
    index = (ROOT / "client" / "index.html").read_text()
    script = (ROOT / "client" / "app.js").read_text()
    stylesheet = (ROOT / "client" / "app.css").read_text()

    assert '<main id="app"' in index
    assert '<script src="/runtime-config.js"></script>' in index
    assert '<script src="/app.js" defer></script>' in index
    assert "{{" not in index
    assert "{%" not in index
    assert "React" not in script
    assert "Vue" not in script
    assert 'window.MLB_API_BASE_URL || "https://localhost:2028"' in script
    assert 'credentials: "include"' in script
    assert "const csrf = state.session?.csrf_token;" in script
    assert 'headers["X-CSRF-TOKEN"] = csrf;' in script
    assert 'cookie("csrf_access_token")' not in script
    assert 'id="manual-sync-button"' in script
    assert 'api("/api/sync/games", { method: "POST", body: {} })' in script
    assert "syncButton.classList.remove(\"is-success\")" in script
    assert 'api("/api/games")' in script
    assert "Math.max(9, linescore.innings.length)" in script
    assert 'id="calendar-game-button"' in script
    assert 'calendarButton.textContent = t("game.addedCalendar")' in script
    assert 'id="calendar-connect"' not in script
    assert 'id="calendar-add"' not in script
    assert 'notice(result.meta.duplicate' not in script
    assert "game-probables detail" in script
    assert "probable-pitcher-stats" in script
    assert "batting-table" in script
    assert 'id="game-boxscore"' in script
    assert "startLiveRefresh(gamePk, game)" in script
    assert "boxscoreSection(game, data.boxscore)" in script
    assert 'turning_points: "走势转折"' in script
    assert 'bullpen_outlook: "牛棚与走势判断"' in script
    assert 'starter_matchup: "先发对决"' in script
    assert 'team_form: "近期状态"' in script
    assert 'outlook: "比赛展望"' in script
    assert '"ai.waitProbables": "等待双方预告先发"' in script
    assert 'pregameAnalysisDisabled ? "btn-secondary" : "btn-danger"' in script
    assert 'error.code === "AI_RATE_LIMITED"' in script
    assert "startAnalysisCooldown(button, error.retryAfter)" in script
    assert 'class="analysis-subsections"' in script
    assert "JSON.stringify(value)" not in script
    assert 'class="schedule-at">@</span>' in script
    assert 'id="date" name="date" type="date"' in script
    assert "const scheduleQuery = selectedDate" in script
    assert 'if (date) next.set("date", date);' in script
    assert 'monthInput.addEventListener("change"' in script
    assert 'if (monthInput.value) dateInput.value = "";' in script
    assert "schedule-team-away" in script
    assert "schedule-team-home" in script
    assert "standings-data-table league-standings-table" in script
    assert "standings-data-table team-stats-table" not in script
    assert "球队打击与投球" not in script
    assert "六赛区排名" not in script
    assert '${t("home.standings")}' in script
    assert '<td><a href="/teams/${team.mlb_team_id}" data-link class="team-link">${logo(team, 28)}' in script
    assert "${logo(team, 30)} ${escapeHtml(team.name)}" in script
    assert "team-week-calendar" in script
    assert 'class="team-calendar-more">${t("team.more")}</a>' in script
    assert '`/api/teams/${teamId}/schedule?month=${encodeURIComponent(selectedMonth)}`' in script
    assert 'id="team-calendar-month" type="month"' in script
    assert 'const lowerSection = monthView' in script
    assert "team-month-calendar" in script
    assert 'teamRosterTier("Active Roster"' in script
    assert 'teamRosterTier(t("team.nonActive")' in script
    assert 'teamRosterColumn(t("team.pitchers")' in script
    assert 'teamRosterColumn(t("team.fielders")' in script
    assert "<strong>Team Roster</strong>" in script
    assert "ERA ${valueOrDash(stats.era)}" in script
    assert "IP ${valueOrDash(stats.innings_pitched)}" in script
    assert "stats.avg != null && stats.hits != null && stats.at_bats != null" in script
    assert "(${valueOrDash(stats.hits)}-${valueOrDash(stats.at_bats)})" in script
    assert ': "AVG -"' in script
    assert "RBI ${valueOrDash(stats.rbi)} · OPS" in script
    assert ".team-roster-columns" in stylesheet
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in stylesheet
    assert ".team-roster-tier.is-other" in stylesheet
    assert ".team-roster-player-stats span { justify-self: start; text-align: left;" in stylesheet
    assert ".team-roster-player-stats.is-pitcher" in stylesheet
    assert "function rosterStatLine(entry, displayRole = entry.role)" in script
    assert "...pitchers.filter((entry) => entry.is_two_way)" in script
    assert "${rows.length - twoWayCount} + 二刀流 ${twoWayCount}" in script
    assert "function activeRosterSection(activeRosters)" in script
    assert 'id="game-active-roster"' in script
    assert '["pitchers", "投手"]' in script
    assert '["catchers", "捕手"]' in script
    assert '["infielders", "内野手"]' in script
    assert '["outfielders", "外野手"]' in script
    assert "${boxscoreSection(game, boxscore)}\n    ${activeRosterSection(activeRosters)}" in script
    assert "activeRosterSection(data.active_rosters)" in script
    assert ".game-active-roster-grid" in stylesheet
    assert 'class="score-team-link"' in script
    assert 'class="linescore-team-link"' in script
    assert 'class="boxscore-team-heading"><a href="/teams/${game[side].team.mlb_team_id}"' in script
    assert '<div class="game-active-roster-team"><a href="/teams/${roster.team.mlb_team_id}"' in script
    assert 'Array.from({ length: 7 }' in script
    assert 'games.length > 1 ? " has-multiple" : ""' in script
    assert "team-calendar-site" not in script
    assert '<span class="team-calendar-away-marker">@</span>' in script
    assert 'isHome ? "" : `<span class="team-calendar-away-marker">@</span>`' not in script
    assert 'result === "W" ? "is-win" : result === "L" ? "is-loss" : "is-tie"' in script
    assert ".team-calendar-result .is-win { color: #198754; }" in stylesheet
    assert ".team-calendar-result .is-loss { color: var(--red); }" in stylesheet
    assert '<b>W:</b>' in script
    assert '<b>S:</b>' in script
    assert '<b>L:</b>' in script
    assert (
        'const divisionNames = ["AL East", "NL East", "AL Central", '
        '"NL Central", "AL West", "NL West"];'
    ) in script


def test_home_decision_labels_align_with_team_logo_column():
    stylesheet = (ROOT / "client" / "app.css").read_text()

    assert (
        ".game-decisions.compact .decision-row { "
        "grid-template-columns: 38px minmax(0, 1fr) auto; gap: .75rem; }"
    ) in stylesheet
    assert ".game-decisions.compact .decision-label { text-align: center; }" in stylesheet


def test_manual_sync_button_has_icon_states():
    stylesheet = (ROOT / "client" / "app.css").read_text()

    assert ".nav-sync-button {" in stylesheet
    assert ".nav-sync-button.is-syncing svg" in stylesheet
    assert ".nav-sync-button.is-success" in stylesheet
    assert "@keyframes nav-sync-spin" in stylesheet


def test_client_supports_chinese_japanese_and_player_detail_extensions():
    index = (ROOT / "client" / "index.html").read_text()
    script = (ROOT / "client" / "app.js").read_text()
    stylesheet = (ROOT / "client" / "app.css").read_text()

    assert 'data-i18n="nav.home"' in index
    assert 'id="language-toggle"' in script
    assert 'localStorage.getItem("mlb-language")' in script
    assert 'localStorage.setItem("mlb-language", state.language)' in script
    assert '"home.title": "本日の MLB 試合"' in script
    assert '"schedule.allTeams": "全チーム"' in script
    assert '"game.aiFinal": "AI 試合後まとめ"' in script
    assert '?lang=${state.language}' in script
    assert 'body: { language: state.language }' in script
    assert 'href="/players/${row.player_id}" data-link class="boxscore-player-link"' in script
    assert 'id="refresh-state"' not in script
    assert '最近刷新' not in script
    assert 'id="player-analysis-button"' in script
    assert 'data.recent_appearances' in script
    assert '/players/${playerId}/analyses' in script
    assert '.player-recent-table' in stylesheet
    assert '.nav-language-button' in stylesheet


def test_game_detail_tables_use_compact_fixed_columns():
    script = (ROOT / "client" / "app.js").read_text()
    stylesheet = (ROOT / "client" / "app.css").read_text()

    assert ".linescore-table {" in stylesheet
    assert 'game-summary-heading${decisions ? " has-decisions" : ""}' in script
    assert 'class="game-summary-side-title">${t("game.decisions")}</span>' in script
    assert '<h3>${t("game.probables")}</h3>' in script
    assert "grid-template-columns: minmax(0, 1fr) minmax(285px, 315px)" in stylesheet
    assert "grid-template-rows: repeat(3, minmax(0, 1fr))" in stylesheet
    assert ".batting-table col.stat-pos { width: 6%; }" in stylesheet
    assert ".batting-table col.stat-player { width: 16%; }" in stylesheet
    assert (
        ".batting-table col.stat-number,\n"
        ".pitching-table col.stat-number { width: 9.75%; }"
    ) in stylesheet
    assert ".pitching-table col.stat-player { width: 22%; }" in stylesheet
    assert ".calendar-game-button.is-added" in stylesheet


def test_schedule_and_standings_tables_have_stable_alignment_rules():
    stylesheet = (ROOT / "client" / "app.css").read_text()

    assert ".schedule-table { min-width: 760px; table-layout: fixed; }" in stylesheet
    assert "grid-template-columns: 5.5rem 1rem 5.5rem" in stylesheet
    assert ".schedule-team-away { justify-self: end; }" in stylesheet
    assert ".schedule-team-home { justify-self: start; }" in stylesheet
    assert (
        ".standings-data-table { min-width: 1100px; table-layout: fixed;"
        in stylesheet
    )
    assert (
        ".standings-data-table th:first-child, "
        ".standings-data-table td:first-child { padding-left: 1.25rem; width: 250px; }"
        in stylesheet
    )
    assert ".team-stats-table" not in stylesheet
    assert ".team-calendar-day.is-home { background: #f0f6ff; }" in stylesheet
    assert (
        ".team-calendar-day.is-today { background: #fff6d9; "
        "box-shadow: inset 0 0 0 2px #e0ad24; }"
    ) in stylesheet
    assert "height: 260px" in stylesheet
    assert ".team-calendar-card-heading" in stylesheet
    assert ".team-month-switcher" in stylesheet
    assert ".team-month-calendar .team-calendar-day" in stylesheet
    assert (
        ".team-calendar-day.has-multiple .team-logo-wrap "
        "{ --logo-size: 36px !important; }"
    ) in stylesheet


def test_client_and_api_are_separate_docker_services():
    compose = (ROOT / "docker-compose.yml").read_text()
    dockerfile = (ROOT / "client" / "Dockerfile").read_text()
    static_server = (ROOT / "client" / "server.py").read_text()

    assert "\n  api:\n" in compose
    assert "\n  client:\n" in compose
    assert '"2027:2027"' in compose
    assert '"2028:2027"' in compose
    assert "nginx" not in dockerfile.casefold()
    assert "ThreadingHTTPServer" in static_server
    assert 'self.path = "/index.html"' in static_server


def test_api_root_is_json_and_discoverable(client):
    response = client.get("/api")
    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()["data"]["resources"]["games"] == "/api/games"


def test_api_allows_credentialed_cors_from_client_origin(client):
    response = client.get(
        "/api/health",
        headers={"Origin": "https://localhost:2027"},
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://localhost:2027"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


def test_api_rejects_unknown_cors_origin(client):
    response = client.get(
        "/api/health",
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


def test_api_answers_cors_preflight_for_json_and_csrf_headers(client):
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://localhost:2027",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://localhost:2027"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    allowed_headers = response.headers["Access-Control-Allow-Headers"].casefold()
    assert "content-type" in allowed_headers
    assert "x-csrf-token" in allowed_headers
