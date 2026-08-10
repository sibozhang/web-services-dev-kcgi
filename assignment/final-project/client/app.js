const app = document.querySelector("#app");
const authNav = document.querySelector("#auth-nav");
const state = {
  session: null,
  meta: { season: 2026, timezone: "Asia/Tokyo" },
  language: localStorage.getItem("mlb-language") === "ja" ? "ja" : "zh",
};
let liveTimer = null;
let syncButtonResetTimer = null;
const API_BASE_URL = (window.MLB_API_BASE_URL || "https://localhost:2028").replace(/\/$/, "");

const STATUS = {
  SCHEDULED: ["primary", "status.scheduled"],
  LIVE: ["danger", "status.live"],
  FINAL: ["dark", "status.final"],
  DELAYED: ["warning", "status.delayed"],
  POSTPONED: ["warning", "status.postponed"],
  SUSPENDED: ["warning", "status.suspended"],
  CANCELLED: ["secondary", "status.cancelled"],
  UNKNOWN: ["secondary", "status.unknown"],
};

const MESSAGES = {
  zh: {
    "nav.home": "首页", "nav.schedule": "日程", "nav.standings": "排名", "nav.teams": "球队", "nav.players": "球员数据",
    "nav.logout": "退出", "nav.login": "登录", "nav.register": "注册", "nav.switch": "日本語",
    "sync.label": "同步比赛数据", "sync.running": "正在同步比赛数据…", "sync.done": "同步完成", "sync.failed": "同步失败",
    "status.scheduled": "未开始", "status.live": "比赛中", "status.final": "比赛结束", "status.delayed": "延迟",
    "status.postponed": "延期", "status.suspended": "暂停", "status.cancelled": "取消", "status.unknown": "状态待确认",
    "home.timezone": "日本时间", "home.title": "今日 MLB 比赛", "home.subtitle": "今日赛程、实时状态与联盟排名。",
    "home.gameCount": "场比赛", "home.allGames": "全部比赛", "home.empty": "今天没有比赛。", "home.starter": "先发",
    "home.pending": "待定", "home.standings": "分区排名", "home.fullStandings": "查看完整排名",
    "schedule.title": "MLB 日程", "schedule.date": "日期（JST）", "schedule.month": "月份", "schedule.team": "球队",
    "schedule.filter": "筛选", "schedule.allTeams": "全部球队", "schedule.matchup": "对阵", "schedule.status": "状态",
    "schedule.scoreTime": "比分 / 时间", "standings.title": "联盟排名", "teams.title": "MLB 球队",
    "players.title": "球员数据", "players.step": "第一步：选择球队", "players.select": "请选择球队",
    "players.showRoster": "显示 Roster", "players.player": "球员", "players.position": "位置", "players.status": "状态",
    "team.week": "一周比赛", "team.more": "展开更多日程", "team.nonActive": "非 Active 名单",
    "team.month": "整月日程", "team.back": "返回一周比赛", "team.pitchers": "投手", "team.fielders": "野手",
    "game.addCalendar": "添加到日历", "game.addedCalendar": "已添加", "game.linescore": "各局得分",
    "game.decisions": "责任投手", "game.probables": "预告先发", "game.boxscore": "比赛数据",
    "game.aiLive": "AI 比赛中分析", "game.aiFinal": "AI 赛后总结", "game.aiPregame": "AI 赛前展望",
    "ai.generate": "生成分析", "ai.update": "更新分析", "ai.waitProbables": "等待双方预告先发",
    "ai.generated": "AI 分析已生成。", "ai.cached": "已显示最近一次 AI 分析。", "ai.retry": "请在 {seconds} 秒后重试",
    "player.recent": "近期出场成绩", "player.ai": "球员 AI 分析", "player.noRecent": "暂无近期出场记录。",
    "footer.timezone": "日本标准时间（JST）", "footer.updated": "最后更新：{time}",
    "common.team": "Team", "common.noData": "暂无数据",
  },
  ja: {
    "nav.home": "ホーム", "nav.schedule": "日程", "nav.standings": "順位", "nav.teams": "チーム", "nav.players": "選手データ",
    "nav.logout": "ログアウト", "nav.login": "ログイン", "nav.register": "登録", "nav.switch": "中文",
    "sync.label": "試合データを同期", "sync.running": "試合データを同期中…", "sync.done": "同期完了", "sync.failed": "同期失敗",
    "status.scheduled": "試合前", "status.live": "試合中", "status.final": "試合終了", "status.delayed": "遅延",
    "status.postponed": "延期", "status.suspended": "中断", "status.cancelled": "中止", "status.unknown": "状態確認中",
    "home.timezone": "日本時間", "home.title": "本日の MLB 試合", "home.subtitle": "本日の試合日程、ライブ状況、順位。",
    "home.gameCount": "試合", "home.allGames": "全試合", "home.empty": "本日の試合はありません。", "home.starter": "先発",
    "home.pending": "未定", "home.standings": "地区順位", "home.fullStandings": "順位表を見る",
    "schedule.title": "MLB 日程", "schedule.date": "日付（JST）", "schedule.month": "月", "schedule.team": "チーム",
    "schedule.filter": "絞り込み", "schedule.allTeams": "全チーム", "schedule.matchup": "対戦", "schedule.status": "状態",
    "schedule.scoreTime": "スコア / 時刻", "standings.title": "リーグ順位", "teams.title": "MLB チーム",
    "players.title": "選手データ", "players.step": "ステップ1：チームを選択", "players.select": "チームを選択",
    "players.showRoster": "Rosterを表示", "players.player": "選手", "players.position": "守備位置", "players.status": "状態",
    "team.week": "1週間の試合", "team.more": "日程をもっと見る", "team.nonActive": "非Activeロースター",
    "team.month": "月間日程", "team.back": "1週間の試合に戻る", "team.pitchers": "投手", "team.fielders": "野手",
    "game.addCalendar": "カレンダーに追加", "game.addedCalendar": "追加済み", "game.linescore": "イニング別得点",
    "game.decisions": "責任投手", "game.probables": "予告先発", "game.boxscore": "試合データ",
    "game.aiLive": "AI 試合中分析", "game.aiFinal": "AI 試合後まとめ", "game.aiPregame": "AI 試合前展望",
    "ai.generate": "分析を生成", "ai.update": "分析を更新", "ai.waitProbables": "両チームの予告先発を待っています",
    "ai.generated": "AI分析を生成しました。", "ai.cached": "直近のAI分析を表示しました。", "ai.retry": "{seconds}秒後に再試行してください",
    "player.recent": "直近の出場成績", "player.ai": "選手 AI 分析", "player.noRecent": "直近の出場記録はありません。",
    "footer.timezone": "日本標準時（JST）", "footer.updated": "最終更新：{time}",
    "common.team": "Team", "common.noData": "データなし",
  },
};

function t(key, variables = {}) {
  let value = MESSAGES[state.language]?.[key] || MESSAGES.zh[key] || key;
  Object.entries(variables).forEach(([name, replacement]) => {
    value = value.replaceAll(`{${name}}`, String(replacement));
  });
  return value;
}

function rankLabel(rank) {
  if (rank === null || rank === undefined || rank === "") return "—";
  return state.language === "ja" ? `${rank}位` : `第${rank}名`;
}

function inningLabel(inning, half) {
  const number = valueOrDash(inning);
  if (state.language !== "ja") return `${number} 局 ${escapeHtml(half || "")}`;
  const normalized = String(half || "").toLowerCase();
  const japaneseHalf = normalized.includes("top") ? "表"
    : normalized.includes("bottom") ? "裏"
      : normalized.includes("middle") ? "中" : normalized.includes("end") ? "終了" : half || "";
  return `${number}回${escapeHtml(japaneseHalf)}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function valueOrDash(value) {
  return value === null || value === undefined || value === "" ? "—" : escapeHtml(value);
}

async function api(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const csrf = state.session?.csrf_token;
  if (csrf && !["GET", "HEAD"].includes((options.method || "GET").toUpperCase())) {
    headers["X-CSRF-TOKEN"] = csrf;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...options,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error?.message || "请求失败，请稍后重试。");
    error.status = response.status;
    error.code = payload.error?.code;
    error.retryAfter = Number(payload.error?.retry_after || 0);
    throw error;
  }
  return payload;
}

function logo(team, size = 48) {
  return `<span class="team-logo-wrap" style="--logo-size:${size}px">
    <img src="${escapeHtml(team.logo_url || "")}" alt="${escapeHtml(team.name)} logo" class="team-logo"
      onerror="this.hidden=true;this.nextElementSibling.hidden=false">
    <span class="logo-fallback" hidden>${escapeHtml(team.abbreviation)}</span>
  </span>`;
}

function statusBadge(game) {
  const status = game.status?.normalized || "UNKNOWN";
  const [color, labelKey] = STATUS[status] || STATUS.UNKNOWN;
  return `<span class="badge text-bg-${color}">${t(labelKey)}</span>`;
}

function formatJst(value, options = {}) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(state.language === "ja" ? "ja-JP" : "zh-CN", {
    timeZone: "Asia/Tokyo",
    ...options,
  }).format(new Date(value));
}

function shortDateTime(value) {
  return formatJst(value, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function fullDateTime(value) {
  return formatJst(value, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function dateOnly(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function addDateOnly(value, days) {
  const result = dateOnly(value);
  result.setUTCDate(result.getUTCDate() + days);
  return result.toISOString().slice(0, 10);
}

function datePartsJp(value) {
  const date = dateOnly(value);
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  return {
    month: date.getUTCMonth() + 1,
    day: date.getUTCDate(),
    weekday: weekdays[date.getUTCDay()],
  };
}

function updateFooter() {
  const timezone = document.querySelector("#footer-timezone");
  if (timezone) timezone.textContent = t("footer.timezone");
  const updated = document.querySelector("#last-updated");
  updated.textContent = state.meta.last_updated
    ? ` · ${t("footer.updated", { time: fullDateTime(state.meta.last_updated) })}`
    : "";
}

function applyStaticTranslations() {
  document.documentElement.lang = state.language === "ja" ? "ja" : "zh-CN";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  updateFooter();
}

function decisionLine(decision) {
  const stats = decision.season_stats || {};
  const record = decision.code === "S"
    ? `SV ${valueOrDash(stats.saves)}`
    : `${valueOrDash(stats.wins)}–${valueOrDash(stats.losses)}`;
  return `<div class="decision-row">
    <span class="decision-label">${decision.code}</span>
    <span class="decision-name">${escapeHtml(decision.pitcher.full_name)}</span>
    <span class="decision-stats">${record} · ERA ${valueOrDash(stats.era)}</span>
  </div>`;
}

function gameCard(game) {
  const awayRecord = game.away.standing
    ? `<small class="team-season-record">${game.away.standing.wins}–${game.away.standing.losses}</small>`
    : "";
  const homeRecord = game.home.standing
    ? `<small class="team-season-record">${game.home.standing.wins}–${game.home.standing.losses}</small>`
    : "";
  let footer = "";
  if (game.status.normalized === "LIVE") {
    footer = `<p class="live-line mb-0 mt-3">${inningLabel(game.status.current_inning, game.status.inning_half)}</p>`;
  } else if (game.status.normalized === "SCHEDULED") {
    footer = `<p class="small text-secondary mb-0 mt-3">${t("home.starter")}：${
      escapeHtml(game.away.probable_pitcher?.full_name || t("home.pending"))
    } / ${escapeHtml(game.home.probable_pitcher?.full_name || t("home.pending"))}</p>`;
  } else if (game.status.normalized === "FINAL" && game.decisions.length) {
    footer = `<div class="game-decisions compact mt-3">${game.decisions.map(decisionLine).join("")}</div>`;
  }
  return `<a class="card game-card h-100 text-decoration-none" href="/games/${game.game_pk}" data-link>
    <div class="card-body">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <small class="text-secondary">${shortDateTime(game.start_time_utc)} JST</small>
        ${statusBadge(game)}
      </div>
      <div class="team-row">
        ${logo(game.away.team, 38)}
        <span class="flex-grow-1"><span class="team-name">${escapeHtml(game.away.team.name)}</span>${awayRecord}</span>
        <strong>${valueOrDash(game.away.score)}</strong>
      </div>
      <div class="team-row">
        ${logo(game.home.team, 38)}
        <span class="flex-grow-1"><span class="team-name">${escapeHtml(game.home.team.name)}</span>${homeRecord}</span>
        <strong>${valueOrDash(game.home.score)}</strong>
      </div>
      ${footer}
    </div>
  </a>`;
}

function notice(message, category = "success") {
  const element = document.createElement("div");
  element.className = `alert alert-${category} alert-dismissible fade show`;
  element.setAttribute("role", "alert");
  element.innerHTML = `${escapeHtml(message)}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
  app.prepend(element);
}

function startAnalysisCooldown(button, seconds) {
  let remaining = Math.max(1, Number(seconds) || 60);
  let timer = null;
  const originalText = button.textContent;
  button.disabled = true;
  button.dataset.cooldown = "true";
  button.classList.remove("btn-danger");
  button.classList.add("btn-secondary");
  const update = () => {
    button.textContent = t("ai.retry", { seconds: remaining });
    remaining -= 1;
    if (remaining < 0 || !button.isConnected) {
      if (timer) clearInterval(timer);
      if (button.isConnected) {
        button.textContent = originalText;
        button.disabled = false;
        button.dataset.cooldown = "false";
        button.classList.remove("btn-secondary");
        button.classList.add("btn-danger");
      }
    }
  };
  update();
  timer = setInterval(update, 1000);
}

function loading() {
  app.innerHTML = `<div class="empty-state">${state.language === "ja" ? "試合データを読み込み中…" : "正在读取比赛数据…"}</div>`;
}

function renderNav() {
  const user = state.session?.user;
  const languageButton = `<button class="btn btn-sm btn-outline-light nav-language-button me-2" id="language-toggle" type="button"
    aria-label="${state.language === "ja" ? "切换为中文" : "日本語に切り替え"}">${t("nav.switch")}</button>`;
  authNav.innerHTML = user
    ? `${languageButton}<button class="btn btn-sm btn-outline-light nav-sync-button me-3" id="manual-sync-button" type="button"
         aria-label="${t("sync.label")}" title="${t("sync.label")}">
         <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6v5h-5M4 18v-5h5M6.1 9a7 7 0 0 1 11.4-2.2L20 9M4 15l2.5 2.2A7 7 0 0 0 17.9 15"/></svg>
       </button>
       <span class="navbar-text me-3 small">${escapeHtml(user.email)}</span>
       <button class="btn btn-sm btn-outline-light" id="logout-button">${t("nav.logout")}</button>`
    : `${languageButton}<a class="btn btn-sm btn-outline-light me-2" href="/login" data-link>${t("nav.login")}</a>
       <a class="btn btn-sm btn-danger" href="/register" data-link>${t("nav.register")}</a>`;
  document.querySelector("#language-toggle")?.addEventListener("click", async () => {
    state.language = state.language === "zh" ? "ja" : "zh";
    localStorage.setItem("mlb-language", state.language);
    applyStaticTranslations();
    renderNav();
    await route();
  });
  const syncButton = document.querySelector("#manual-sync-button");
  syncButton?.addEventListener("click", async () => {
    clearTimeout(syncButtonResetTimer);
    syncButton.disabled = true;
    syncButton.classList.remove("is-success", "is-error");
    syncButton.classList.add("is-syncing");
    syncButton.setAttribute("aria-busy", "true");
    syncButton.title = t("sync.running");
    try {
      const result = await api("/api/sync/games", { method: "POST", body: {} });
      state.meta.last_updated = result.data.completed_at;
      updateFooter();
      await route();
      syncButton.classList.add("is-success");
      syncButton.title = t("sync.done");
      notice(result.message || "比赛数据同步完成。");
      syncButtonResetTimer = setTimeout(() => {
        syncButton.classList.remove("is-success");
        syncButton.title = t("sync.label");
      }, 1600);
    } catch (error) {
      syncButton.classList.add("is-error");
      syncButton.title = t("sync.failed");
      if (!requireLogin(error)) notice(error.message, "danger");
      syncButtonResetTimer = setTimeout(() => {
        syncButton.classList.remove("is-error");
        syncButton.title = t("sync.label");
      }, 2500);
    } finally {
      syncButton.disabled = false;
      syncButton.classList.remove("is-syncing");
      syncButton.removeAttribute("aria-busy");
    }
  });
  document.querySelector("#logout-button")?.addEventListener("click", async () => {
    try {
      await api("/api/auth/logout", { method: "POST", body: {} });
      state.session = { authenticated: false, user: null };
      renderNav();
      navigate("/");
    } catch (error) {
      notice(error.message, "danger");
    }
  });
}

function setTitle(title) {
  document.title = `${title} · MLB Dugout`;
}

function standingsTable(rows, compact = false) {
  if (!rows?.length) {
    return `<tr><td colspan="${compact ? 5 : 12}" class="text-secondary py-3 text-center">暂无排名数据</td></tr>`;
  }
  return rows.map(({ team, standing }) => compact
    ? `<tr>
        <td><a href="/teams/${team.mlb_team_id}" data-link class="team-link">${logo(team, 28)} ${escapeHtml(team.abbreviation)}</a></td>
        <td>${standing.wins}</td><td>${standing.losses}</td>
        <td>${valueOrDash(standing.winning_percentage)}</td><td>${valueOrDash(standing.games_back)}</td>
      </tr>`
    : `<tr>
        <td><a href="/teams/${team.mlb_team_id}" data-link class="team-link">${logo(team, 30)} ${escapeHtml(team.name)}</a></td>
        <td>${standing.wins}</td><td>${standing.losses}</td><td>${valueOrDash(standing.winning_percentage)}</td><td>${valueOrDash(standing.games_back)}</td>
        <td>${standing.last_ten.wins}-${standing.last_ten.losses}</td><td>${valueOrDash(standing.streak)}</td>
        <td>${standing.home.wins}-${standing.home.losses}</td><td>${standing.away.wins}-${standing.away.losses}</td>
        <td>${valueOrDash(standing.runs_scored)}</td><td>${valueOrDash(standing.runs_allowed)}</td>
        <td class="${standing.run_differential > 0 ? "text-success" : standing.run_differential < 0 ? "text-danger" : ""}">${standing.run_differential > 0 ? "+" : ""}${standing.run_differential}</td>
      </tr>`).join("");
}

async function renderHome() {
  setTitle(t("home.title"));
  const [gamesResponse, standingsResponse] = await Promise.all([
    api("/api/games"),
    api(`/api/standings?season=${state.meta.season}`),
  ]);
  const games = gamesResponse.data;
  const divisions = standingsResponse.data.divisions;
  const [year, month, day] = gamesResponse.meta.date.split("-");
  const dateValue = state.language === "ja" ? `${year}年${month}月${day}日` : `${year}年${month}月${day}日`;
  const divisionNames = ["AL East", "NL East", "AL Central", "NL Central", "AL West", "NL West"];
  app.innerHTML = `<section class="hero-panel mb-4">
    <div>
      <p class="eyebrow mb-2">${t("home.timezone")} · ${escapeHtml(dateValue)}</p>
      <h1 class="display-5 fw-bold mb-2">${t("home.title")}</h1>
      <p class="mb-0 text-white-50">${t("home.subtitle")}</p>
    </div>
    <div class="hero-stat"><span>${games.length}</span><small>${t("home.gameCount")}</small></div>
  </section>
  <section class="mb-5">
    <div class="section-heading"><div><p class="eyebrow text-danger mb-1">TODAY</p><h2 class="h4 mb-0">${t("home.allGames")}</h2></div></div>
    ${games.length
      ? `<div class="row g-3">${games.map((game) => `<div class="col-md-6 col-xl-4">${gameCard(game)}</div>`).join("")}</div>`
      : `<div class="empty-state">${t("home.empty")}</div>`}
  </section>
  <section>
    <div class="section-heading">
      <div><p class="eyebrow text-danger mb-1">${state.meta.season} SEASON</p><h2 class="h4 mb-0">${t("home.standings")}</h2></div>
      <a href="/standings" data-link class="btn btn-outline-dark btn-sm">${t("home.fullStandings")}</a>
    </div>
    <div class="row g-3">${divisionNames.map((name) => `<div class="col-lg-6">
      <div class="card standings-card">
        <div class="card-header">${name}</div>
        <div class="table-responsive"><table class="table table-sm mb-0 align-middle">
          <thead><tr><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>GB</th></tr></thead>
          <tbody>${standingsTable(divisions[name], true)}</tbody>
        </table></div>
      </div>
    </div>`).join("")}</div>
  </section>`;
}

async function renderSchedule() {
  setTitle(t("schedule.title"));
  const params = new URLSearchParams(location.search);
  const selectedDate = params.get("date") || "";
  const month = params.get("month") || selectedDate.slice(0, 7) || new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit" }).slice(0, 7);
  const team = params.get("team") || "";
  const scheduleQuery = selectedDate
    ? `date=${encodeURIComponent(selectedDate)}`
    : `month=${encodeURIComponent(month)}`;
  const [teamsResponse, gamesResponse] = await Promise.all([
    api("/api/teams"),
    api(`/api/games?${scheduleQuery}${team ? `&team=${encodeURIComponent(team)}` : ""}`),
  ]);
  app.innerHTML = `<div class="section-heading"><div><p class="eyebrow text-danger mb-1">GAME SCHEDULE</p><h1 class="h2">${t("schedule.title")}</h1></div></div>
  <form id="schedule-filter" class="filter-bar row g-3 align-items-end mb-4">
    <div class="col-md-3"><label class="form-label" for="date">${t("schedule.date")}</label><input class="form-control" id="date" name="date" type="date" value="${escapeHtml(selectedDate)}"></div>
    <div class="col-md-3"><label class="form-label" for="month">${t("schedule.month")}</label><input class="form-control" id="month" name="month" type="month" value="${escapeHtml(month)}"></div>
    <div class="col-md-4"><label class="form-label" for="team">${t("schedule.team")}</label><select class="form-select" id="team" name="team">
      <option value="">${t("schedule.allTeams")}</option>
      ${teamsResponse.data.map((item) => `<option value="${item.mlb_team_id}" ${String(item.mlb_team_id) === team ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}
    </select></div>
    <div class="col-md-2"><button class="btn btn-danger w-100">${t("schedule.filter")}</button></div>
  </form>
  ${gamesResponse.data.length ? `<div class="card"><div class="table-responsive">
    <table class="table align-middle mb-0 schedule-table">
    <colgroup><col class="schedule-date-column"><col class="schedule-matchup-column"><col class="schedule-status-column"><col class="schedule-result-column"></colgroup>
    <thead><tr><th>${t("schedule.date")}</th><th>${t("schedule.matchup")}</th><th>${t("schedule.status")}</th><th>${t("schedule.scoreTime")}</th></tr></thead>
    <tbody>${gamesResponse.data.map((game) => `<tr>
      <td>${formatJst(game.start_time_utc, { month: "2-digit", day: "2-digit", weekday: "short" })}</td>
      <td><span class="schedule-matchup">
        <span class="schedule-team schedule-team-away">${logo(game.away.team, 30)}<span>${escapeHtml(game.away.team.abbreviation)}</span></span>
        <span class="schedule-at">@</span>
        <span class="schedule-team schedule-team-home">${logo(game.home.team, 30)}<span>${escapeHtml(game.home.team.abbreviation)}</span></span>
      </span></td>
      <td>${statusBadge(game)}</td>
      <td><a href="/games/${game.game_pk}" data-link>${
        game.status.normalized === "FINAL" ? `${valueOrDash(game.away.score)}–${valueOrDash(game.home.score)}`
          : game.status.normalized === "SCHEDULED" ? formatJst(game.start_time_utc, { hour: "2-digit", minute: "2-digit", hour12: false })
          : escapeHtml(game.status.detailed || "查看详情")
      }</a></td>
    </tr>`).join("")}</tbody></table>
  </div></div>` : `<div class="empty-state">该筛选条件下没有比赛，请调整日期、月份或球队。</div>`}`;
  const dateInput = document.querySelector("#date");
  const monthInput = document.querySelector("#month");
  dateInput.addEventListener("change", () => {
    if (dateInput.value) monthInput.value = dateInput.value.slice(0, 7);
  });
  monthInput.addEventListener("change", () => {
    if (monthInput.value) dateInput.value = "";
  });
  document.querySelector("#schedule-filter").addEventListener("submit", (event) => {
    event.preventDefault();
    const next = new URLSearchParams();
    const date = dateInput.value;
    if (date) next.set("date", date);
    else next.set("month", monthInput.value);
    const selected = document.querySelector("#team").value;
    if (selected) next.set("team", selected);
    navigate(`/schedule?${next}`);
  });
}

async function renderStandings() {
  setTitle(t("standings.title"));
  const { data } = await api(`/api/standings?season=${state.meta.season}`);
  const names = ["AL East", "AL Central", "AL West", "NL East", "NL Central", "NL West"];
  app.innerHTML = `<div class="section-heading"><div><p class="eyebrow text-danger mb-1">${data.season} SEASON</p><h1 class="h2">${t("standings.title")}</h1></div></div>
  ${names.map((name) => `<section class="card mb-4">
    <div class="card-header fw-bold">${name}</div><div class="table-responsive">
      <table class="table table-hover align-middle mb-0 standings-data-table league-standings-table"><thead><tr><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>GB</th><th>L10</th><th>Streak</th><th>Home</th><th>Away</th><th>RS</th><th>RA</th><th>DIFF</th></tr></thead>
      <tbody>${standingsTable(data.divisions[name])}</tbody></table>
    </div>
  </section>`).join("")}`;
}

async function renderTeams() {
  setTitle(t("teams.title"));
  const { data: teams } = await api("/api/teams");
  const leagues = ["AL", "NL"];
  app.innerHTML = `<div class="section-heading"><div><p class="eyebrow text-danger mb-1">30 CLUBS</p><h1 class="h2">${t("teams.title")}</h1></div></div>
  ${leagues.map((league) => `<section class="mb-5"><h2 class="h4 mb-3">${league === "AL" ? "American League" : "National League"}</h2>
    ${["East", "Central", "West"].map((suffix) => {
      const division = `${league} ${suffix}`;
      const rows = teams.filter((team) => team.division === division);
      return `<h3 class="division-label">${division}</h3><div class="row g-3 mb-4">${
        rows.length ? rows.map((team) => `<div class="col-sm-6 col-lg-4"><a class="card team-card text-decoration-none" href="/teams/${team.mlb_team_id}" data-link>
          <div class="card-body d-flex align-items-center gap-3">${logo(team, 58)}<div><strong>${escapeHtml(team.name)}</strong><div class="text-secondary small">${escapeHtml(team.abbreviation)}</div></div></div>
        </a></div>`).join("") : `<div class="col-12 text-secondary small">该赛区暂无球队数据。</div>`
      }</div>`;
    }).join("")}
  </section>`).join("")}`;
}

function requireLogin(error) {
  if (error.status !== 401) return false;
  navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`);
  return true;
}

function rosterPitchHand(value) {
  if (value === "Left") return "左投";
  if (value === "Right") return "右投";
  return valueOrDash(value);
}

function rosterAvgDetails(stats) {
  const hasHittingStats = stats.avg != null && stats.hits != null && stats.at_bats != null;
  return hasHittingStats
    ? `AVG ${valueOrDash(stats.avg)} (${valueOrDash(stats.hits)}-${valueOrDash(stats.at_bats)})`
    : "AVG -";
}

function rosterStatLine(entry, displayRole = entry.role) {
  const stats = entry.season_stats || {};
  if (displayRole === "pitcher") {
    return {
      modifier: "is-pitcher",
      html: `<span>${rosterPitchHand(entry.player.pitch_hand)}</span><span>ERA ${valueOrDash(stats.era)}</span><span>IP ${valueOrDash(stats.innings_pitched)}</span>`,
    };
  }
  return {
    modifier: "is-position-player",
    html: `<span>${escapeHtml(entry.position || "—")}</span><span>${rosterAvgDetails(stats)}</span><span>RBI ${valueOrDash(stats.rbi)} · OPS ${valueOrDash(stats.ops)}</span>`,
  };
}

function teamRosterColumn(title, rows, role) {
  const twoWayCount = role === "position_player"
    ? rows.filter((entry) => entry.is_two_way).length
    : 0;
  const countLabel = twoWayCount
    ? `${rows.length - twoWayCount} + 二刀流 ${twoWayCount}`
    : rows.length;
  const playerRow = (entry) => {
    const details = rosterStatLine(entry, role);
    return `<a class="team-roster-player" href="/players/${entry.player.mlb_player_id}" data-link>
      <strong>${escapeHtml(entry.player.full_name)}</strong>
      <span class="team-roster-player-stats ${details.modifier}">${details.html}</span>
      ${entry.is_active_roster ? "" : `<small>${escapeHtml(entry.roster_status || "40-man roster")}</small>`}
    </a>`;
  };
  return `<div class="team-roster-column">
    <h4>${title}<span>${countLabel}</span></h4>
    <div class="team-roster-list">${rows.length ? rows.map(playerRow).join("") : `<div class="team-roster-empty">${state.language === "ja" ? "選手なし" : "暂无球员"}</div>`}</div>
  </div>`;
}

function teamRosterTier(title, group, count, modifier = "") {
  const pitchers = group.pitchers || [];
  const positionPlayers = [
    ...(group.position_players || []),
    ...pitchers.filter((entry) => entry.is_two_way),
  ];
  return `<section class="team-roster-tier ${modifier}">
    <div class="team-roster-tier-heading"><strong>${title}</strong><span>${count} 人</span></div>
    <div class="team-roster-columns">
      ${teamRosterColumn(t("team.pitchers"), pitchers, "pitcher")}
      ${teamRosterColumn(t("team.fielders"), positionPlayers, "position_player")}
    </div>
  </section>`;
}

function teamRosterCard(roster) {
  const counts = roster.counts || {};
  return `<section class="card team-roster-card">
    <div class="card-header team-roster-card-heading"><strong>Team Roster</strong><span>${valueOrDash(counts.total)} 人</span></div>
    ${teamRosterTier("Active Roster", roster.active || {}, counts.active || 0, "is-active")}
    ${teamRosterTier(t("team.nonActive"), roster.other || {}, counts.other || 0, "is-other")}
  </section>`;
}

async function renderTeamDetail(teamId) {
  try {
    const { data } = await api(`/api/teams/${teamId}`);
    const team = data.team;
    const params = new URLSearchParams(location.search);
    const monthView = params.get("view") === "calendar";
    const selectedMonth = params.get("month") || data.game_window.today.slice(0, 7);
    const monthData = monthView
      ? (await api(`/api/teams/${teamId}/schedule?month=${encodeURIComponent(selectedMonth)}`)).data
      : null;
    setTitle(team.name);
    const record = data.standing ? `<div class="record-box">
      <p class="eyebrow mb-1">${escapeHtml(team.division)} · ${rankLabel(data.standing.division_rank)}</p>
      <strong>${data.standing.wins}–${data.standing.losses}</strong>
      <small>${valueOrDash(data.standing.winning_percentage)}</small>
    </div>` : "";
    const stats = data.season_stats;
    const calendarGame = (game) => {
      const isHome = String(game.home.team.mlb_team_id) === String(team.mlb_team_id);
      const opponent = isHome ? game.away.team : game.home.team;
      const ownScore = isHome ? game.home.score : game.away.score;
      const opponentScore = isHome ? game.away.score : game.home.score;
      const isFinal = game.status.normalized === "FINAL" && ownScore !== null && opponentScore !== null;
      let gameState = "";
      let decision = "";
      if (isFinal) {
        const result = ownScore > opponentScore ? "W" : ownScore < opponentScore ? "L" : "–";
        const resultClass = result === "W" ? "is-win" : result === "L" ? "is-loss" : "is-tie";
        gameState = `<div class="team-calendar-result"><span class="${resultClass}">${result}</span> <strong>${ownScore}</strong>–${opponentScore}</div>`;
        if (result === "W") {
          const winner = game.decisions.find((item) => item.code === "W");
          const save = game.decisions.find((item) => item.code === "S");
          decision = winner ? `<div><b>W:</b> ${escapeHtml(winner.pitcher.full_name)}</div>${save ? `<div><b>S:</b> ${escapeHtml(save.pitcher.full_name)}</div>` : ""}` : "";
        } else if (result === "L") {
          const loser = game.decisions.find((item) => item.code === "L");
          decision = loser ? `<div><b>L:</b> ${escapeHtml(loser.pitcher.full_name)}</div>` : "";
        }
      } else if (game.status.normalized === "SCHEDULED") {
        gameState = `<div class="team-calendar-time">${formatJst(game.start_time_utc, { hour: "2-digit", minute: "2-digit", hour12: false })}</div>`;
      } else {
        gameState = `<div class="team-calendar-time">${game.status.normalized === "LIVE" ? t("status.live") : escapeHtml(game.status.detailed || t("status.unknown"))}</div>`;
      }
      return `<a href="/games/${game.game_pk}" data-link class="team-calendar-game">
        ${logo(opponent, 48)}
        <div class="team-calendar-opponent-line">
          <span class="team-calendar-away-marker">@</span>
          <strong class="team-calendar-opponent">${escapeHtml(opponent.abbreviation)}</strong>
        </div>
        ${gameState}
        <span class="team-calendar-venue">${escapeHtml(game.venue_name || "球场待定")}</span>
        ${decision ? `<div class="team-calendar-decision">${decision}</div>` : ""}
      </a>`;
    };
    const calendarDay = (date, games, today, outsideMonth = false) => {
      const dateInfo = datePartsJp(date);
      const isToday = date === today;
      const hasHomeGame = games.some((game) => String(game.home.team.mlb_team_id) === String(team.mlb_team_id));
      return `<div class="team-calendar-day${hasHomeGame ? " is-home" : ""}${isToday ? " is-today" : ""}${games.length > 1 ? " has-multiple" : ""}${outsideMonth ? " is-outside" : ""}">
        <span class="team-calendar-date">${dateInfo.day}</span>
        ${outsideMonth ? "" : games.length ? games.map(calendarGame).join("") : `<span class="team-calendar-off">休赛</span>`}
      </div>`;
    };
    let calendarSection = "";
    if (monthView) {
      const monthStart = monthData.start_date;
      const monthEnd = monthData.end_date;
      const leadingDays = dateOnly(monthStart).getUTCDay();
      const daysInMonth = dateOnly(monthEnd).getUTCDate();
      const cellCount = Math.ceil((leadingDays + daysInMonth) / 7) * 7;
      const gridStart = addDateOnly(monthStart, -leadingDays);
      const calendarDates = Array.from({ length: cellCount }, (_, index) => addDateOnly(gridStart, index));
      const gamesByDate = new Map(calendarDates.map((date) => [date, []]));
      monthData.games.forEach((game) => {
        const date = game.start_time_jst.slice(0, 10);
        if (gamesByDate.has(date)) gamesByDate.get(date).push(game);
      });
      const monthDate = dateOnly(`${monthData.month}-01`);
      const previousMonthDate = new Date(Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth() - 1, 1));
      const nextMonthDate = new Date(Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth() + 1, 1));
      const previousMonth = previousMonthDate.toISOString().slice(0, 7);
      const nextMonth = nextMonthDate.toISOString().slice(0, 7);
      const monthLabel = `${monthDate.getUTCFullYear()}年${monthDate.getUTCMonth() + 1}月`;
      const calendarDays = calendarDates.map((date) => calendarDay(
        date,
        gamesByDate.get(date),
        monthData.today,
        !date.startsWith(monthData.month),
      )).join("");
      calendarSection = `<section class="card team-calendar-card team-month-calendar-card mb-4">
        <div class="card-header team-calendar-card-heading"><strong>${t("team.month")}</strong><a href="/teams/${team.mlb_team_id}" data-link class="team-calendar-more">${t("team.back")}</a></div>
        <div class="team-month-switcher">
          <a href="/teams/${team.mlb_team_id}?view=calendar&month=${previousMonth}" data-link aria-label="上个月">‹</a>
          <label><span>${monthLabel}</span><input id="team-calendar-month" type="month" value="${monthData.month}" aria-label="选择月份"></label>
          <a href="/teams/${team.mlb_team_id}?view=calendar&month=${nextMonth}" data-link aria-label="下个月">›</a>
        </div>
        <div class="table-responsive"><div class="team-week-calendar team-month-calendar">
          <div class="team-calendar-weekdays">${["日", "月", "火", "水", "木", "金", "土"].map((weekday) => `<div>${weekday}</div>`).join("")}</div>
          <div class="team-calendar-days">${calendarDays}</div>
        </div></div>
      </section>`;
    } else {
      const window = data.game_window;
      const calendarDates = Array.from({ length: 7 }, (_, index) => addDateOnly(window.start_date, index));
      const gamesByDate = new Map(calendarDates.map((date) => [date, []]));
      data.games.forEach((game) => {
        const date = game.start_time_jst.slice(0, 10);
        if (gamesByDate.has(date)) gamesByDate.get(date).push(game);
      });
      const rangeStart = datePartsJp(window.start_date);
      const rangeEnd = datePartsJp(window.end_date);
      const calendarDays = calendarDates.map((date) => calendarDay(
        date, gamesByDate.get(date), window.today,
      )).join("");
      calendarSection = `<section class="card team-calendar-card mb-4">
        <div class="card-header team-calendar-card-heading"><strong>${t("team.week")}</strong><a href="/teams/${team.mlb_team_id}?view=calendar&month=${window.today.slice(0, 7)}" data-link class="team-calendar-more">${t("team.more")}</a></div>
        <div class="table-responsive"><div class="team-week-calendar">
          <div class="team-calendar-range">${rangeStart.month}/${rangeStart.day}（${rangeStart.weekday}） 〜 ${rangeEnd.month}/${rangeEnd.day}（${rangeEnd.weekday}）</div>
          <div class="team-calendar-weekdays">${calendarDates.map((date) => `<div>${datePartsJp(date).weekday}</div>`).join("")}</div>
          <div class="team-calendar-days">${calendarDays}</div>
        </div></div>
      </section>`;
    }
    const statsCard = stats ? `<div class="card mb-4"><div class="card-header fw-bold">赛季数据</div><div class="card-body"><div class="stat-grid">
      <div><span>AVG</span><strong>${valueOrDash(stats.batting_avg)}</strong></div><div><span>OPS</span><strong>${valueOrDash(stats.ops)}</strong></div>
      <div><span>HR</span><strong>${valueOrDash(stats.home_runs)}</strong></div><div><span>ERA</span><strong>${valueOrDash(stats.era)}</strong></div>
      <div><span>WHIP</span><strong>${valueOrDash(stats.whip)}</strong></div><div><span>SO</span><strong>${valueOrDash(stats.pitching_strikeouts)}</strong></div>
    </div></div></div>` : "";
    const lowerSection = monthView
      ? statsCard
      : `${statsCard}${teamRosterCard(data.roster)}`;
    app.innerHTML = `<section class="team-hero mb-4">${logo(team, 92)}
      <div><p class="eyebrow mb-1">${escapeHtml(team.division)}</p><h1 class="display-6 fw-bold mb-1">${escapeHtml(team.name)}</h1><p class="mb-0 text-secondary">${escapeHtml(team.venue_name || "球场待定")}</p></div>${record}
    </section>
    ${calendarSection}${lowerSection}`;
    const monthInput = document.querySelector("#team-calendar-month");
    if (monthInput) monthInput.addEventListener("change", () => {
      if (monthInput.value) navigate(`/teams/${team.mlb_team_id}?view=calendar&month=${monthInput.value}`);
    });
  } catch (error) {
    if (!requireLogin(error)) throw error;
  }
}

async function renderPlayers() {
  setTitle(t("players.title"));
  const params = new URLSearchParams(location.search);
  const selectedTeam = params.get("team") || "";
  const teamsResponse = await api("/api/teams");
  const rosterResponse = selectedTeam ? await api(`/api/teams/${selectedTeam}/roster`) : null;
  const rosterEntries = rosterResponse
    ? ["active", "other"].flatMap((tier) => [
        ...(rosterResponse.data.roster[tier]?.pitchers || []),
        ...(rosterResponse.data.roster[tier]?.position_players || []),
      ])
    : [];
  app.innerHTML = `<div class="section-heading"><div><p class="eyebrow text-danger mb-1">TEAM → ROSTER → PLAYER</p><h1 class="h2">${t("players.title")}</h1></div></div>
  <form id="player-filter" class="filter-bar row g-3 align-items-end mb-4">
    <div class="col-md-9"><label for="team" class="form-label">${t("players.step")}</label><select class="form-select" id="team" name="team">
      <option value="">${t("players.select")}</option>${teamsResponse.data.map((team) => `<option value="${team.mlb_team_id}" ${String(team.mlb_team_id) === selectedTeam ? "selected" : ""}>${escapeHtml(team.name)}</option>`).join("")}
    </select></div><div class="col-md-3"><button class="btn btn-danger w-100">${t("players.showRoster")}</button></div>
  </form>
  ${rosterResponse ? `<div class="card"><div class="card-header fw-bold">${escapeHtml(rosterResponse.data.team.name)} Roster</div><div class="table-responsive"><table class="table align-middle mb-0">
    <thead><tr><th>#</th><th>${t("players.player")}</th><th>${t("players.position")}</th><th>${t("players.status")}</th></tr></thead><tbody>
      ${rosterEntries.length ? rosterEntries.map((entry) => `<tr><td>${escapeHtml(entry.jersey_number || "—")}</td><td><a href="/players/${entry.player.mlb_player_id}" data-link>${escapeHtml(entry.player.full_name)}</a></td><td>${escapeHtml(entry.position || "—")}</td><td>${escapeHtml(entry.roster_status || "—")}</td></tr>`).join("") : `<tr><td colspan="4" class="text-center text-secondary py-4">暂无球队名单</td></tr>`}
    </tbody></table></div></div>` : `<div class="empty-state">选择一支球队后显示当前赛季 roster。访客可以选择球员；详情页需要登录。</div>`}`;
  document.querySelector("#player-filter").addEventListener("submit", (event) => {
    event.preventDefault();
    const team = document.querySelector("#team").value;
    navigate(team ? `/players?team=${team}` : "/players");
  });
}

async function renderPlayerDetail(playerId) {
  try {
    const { data } = await api(`/api/players/${playerId}?lang=${state.language}`);
    const player = data.player;
    setTitle(player.full_name);
    const hittingHeaders = ["G", "PA", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB", "AVG", "OBP", "SLG", "OPS"];
    const pitchingHeaders = ["G", "GS", "W", "L", "SV", "IP", "H", "ER", "HR", "BB", "SO", "ERA", "WHIP"];
    const recent = data.recent_appearances || { hitting: [], pitching: [], game_count: 0 };
    const matchupCell = (row) => `<td><a href="/games/${row.game_pk}" data-link class="recent-game-link">${row.is_home ? "vs" : "@"} ${escapeHtml(row.opponent.abbreviation)}</a></td>`;
    const recentHitting = recent.hitting?.length ? `<div class="table-responsive"><table class="table table-sm align-middle mb-0 player-recent-table">
      <thead><tr><th>${state.language === "ja" ? "日付" : "日期"}</th><th>${t("schedule.matchup")}</th><th>Pos</th><th>AB</th><th>R</th><th>H</th><th>RBI</th><th>BB</th><th>K</th><th>AVG</th><th>OPS</th></tr></thead>
      <tbody>${recent.hitting.map((row) => `<tr><td>${formatJst(row.start_time_jst, { month: "2-digit", day: "2-digit" })}</td>${matchupCell(row)}<td>${escapeHtml(row.position)}</td><td>${row.at_bats}</td><td>${row.runs}</td><td>${row.hits}</td><td>${row.rbi}</td><td>${row.walks}</td><td>${row.strikeouts}</td><td>${valueOrDash(row.avg)}</td><td>${valueOrDash(row.ops)}</td></tr>`).join("")}</tbody>
    </table></div>` : "";
    const recentPitching = recent.pitching?.length ? `<div class="table-responsive${recentHitting ? " border-top" : ""}"><table class="table table-sm align-middle mb-0 player-recent-table">
      <thead><tr><th>${state.language === "ja" ? "日付" : "日期"}</th><th>${t("schedule.matchup")}</th><th>IP</th><th>H</th><th>R</th><th>ER</th><th>BB</th><th>K</th><th>HR</th><th>ERA</th></tr></thead>
      <tbody>${recent.pitching.map((row) => `<tr><td>${formatJst(row.start_time_jst, { month: "2-digit", day: "2-digit" })}</td>${matchupCell(row)}<td>${valueOrDash(row.innings)}</td><td>${row.hits}</td><td>${row.runs}</td><td>${row.earned_runs}</td><td>${row.walks}</td><td>${row.strikeouts}</td><td>${row.home_runs}</td><td>${valueOrDash(row.era)}</td></tr>`).join("")}</tbody>
    </table></div>` : "";
    const recentSection = `<section class="card mb-4 player-recent-card"><div class="card-header fw-bold d-flex justify-content-between"><span>${t("player.recent")}</span><small class="text-secondary">${recent.game_count || 0} / 10</small></div>
      ${recentHitting || recentPitching ? `${recentHitting}${recentPitching}` : `<div class="card-body text-secondary">${t("player.noRecent")}</div>`}
    </section>`;
    const playerAnalysis = `<section class="card player-analysis-card"><div class="card-header fw-bold">${t("player.ai")}</div><div class="card-body">
      <div id="player-analyses">${analysisPanels(data.analyses || [])}</div>
      <button class="btn btn-danger" id="player-analysis-button">${data.analyses?.length ? t("ai.update") : t("ai.generate")}</button>
    </div></section>`;
    app.innerHTML = `<div class="player-heading mb-4"><div class="player-avatar">${escapeHtml(player.full_name.slice(0, 1))}</div><div><p class="eyebrow text-danger mb-1">${escapeHtml(player.primary_position || "PLAYER")}</p><h1 class="h2 mb-1">${escapeHtml(player.full_name)}</h1><p class="text-secondary mb-0">Bats: ${escapeHtml(player.bat_side || "—")} · Throws: ${escapeHtml(player.pitch_hand || "—")}</p></div></div>
    ${data.hitting.length ? `<section class="card mb-4"><div class="card-header fw-bold">Hitting · ${data.season}</div><div class="table-responsive"><table class="table mb-0"><thead><tr>${hittingHeaders.map((item) => `<th>${item}</th>`).join("")}</tr></thead><tbody>
      ${data.hitting.map((s) => `<tr>${[s.games_played,s.plate_appearances,s.at_bats,s.runs,s.hits,s.doubles,s.triples,s.home_runs,s.rbi,s.walks,s.strikeouts,s.stolen_bases,s.avg,s.obp,s.slg,s.ops].map((item) => `<td>${valueOrDash(item ?? 0)}</td>`).join("")}</tr>`).join("")}
    </tbody></table></div></section>` : ""}
    ${data.pitching.length ? `<section class="card mb-4"><div class="card-header fw-bold">Pitching · ${data.season}</div><div class="table-responsive"><table class="table mb-0"><thead><tr>${pitchingHeaders.map((item) => `<th>${item}</th>`).join("")}</tr></thead><tbody>
      ${data.pitching.map((s) => `<tr>${[s.games_played,s.games_started,s.wins,s.losses,s.saves,s.innings_pitched,s.hits,s.earned_runs,s.home_runs,s.walks,s.strikeouts,s.era,s.whip].map((item) => `<td>${valueOrDash(item ?? 0)}</td>`).join("")}</tr>`).join("")}
    </tbody></table></div></section>` : ""}
    ${!data.hitting.length && !data.pitching.length ? `<div class="empty-state mb-4">${state.language === "ja" ? "今季の選手成績はありません。" : "暂无该球员的赛季统计。"}</div>` : ""}
    ${recentSection}${playerAnalysis}`;
    document.querySelector("#player-analysis-button").addEventListener("click", async () => {
      const button = document.querySelector("#player-analysis-button");
      let coolingDown = false;
      button.disabled = true;
      try {
        const result = await api(`/api/players/${playerId}/analyses`, {
          method: "POST",
          body: { language: state.language },
        });
        notice(result.meta?.cached ? t("ai.cached") : t("ai.generated"));
        await renderPlayerDetail(playerId);
      } catch (error) {
        if (error.code === "AI_RATE_LIMITED") {
          coolingDown = true;
          startAnalysisCooldown(button, error.retryAfter);
        } else {
          notice(error.message, "warning");
        }
      } finally {
        if (!coolingDown && button.isConnected) button.disabled = false;
      }
    });
  } catch (error) {
    if (!requireLogin(error)) throw error;
  }
}

function linescoreTable(game, linescore) {
  linescore = linescore || { innings: [], totals: { away: {}, home: {} } };
  const inningCount = Math.max(9, linescore.innings.length);
  const headers = Array.from({ length: inningCount }, (_, index) => `<th>${index + 1}</th>`).join("");
  const row = (side) => {
    const team = game[side].team;
    const cells = Array.from({ length: inningCount }, (_, index) => `<td>${valueOrDash(linescore.innings[index]?.[side]?.runs)}</td>`).join("");
    const totals = linescore.totals[side] || {};
    return `<tr><th><a href="/teams/${team.mlb_team_id}" data-link class="linescore-team-link">${escapeHtml(team.abbreviation)}</a></th>${cells}<th>${valueOrDash(totals.runs)}</th><td>${valueOrDash(totals.hits)}</td><td>${valueOrDash(totals.errors)}</td></tr>`;
  };
  const decisions = game.status.normalized === "FINAL" && game.decisions.length
    ? `<aside class="game-decisions detail">${["W", "L", "S"].map((code) => {
        const decision = game.decisions.find((item) => item.code === code);
        return decision ? decisionLine(decision) : `<div class="decision-row is-empty">
          <span class="decision-label">${code}</span><span class="decision-name">—</span><span class="decision-stats">—</span>
        </div>`;
      }).join("")}</aside>`
    : "";
  const probableLine = (side) => {
    const pitcher = game[side].probable_pitcher;
    const stats = pitcher?.season_stats || {};
    return `<div class="probable-pitcher-row">
      <span class="probable-pitcher-name">${escapeHtml(pitcher?.full_name || "尚未公布")}</span>
      <span class="probable-pitcher-stats">${valueOrDash(stats.wins)}–${valueOrDash(stats.losses)} · ERA ${valueOrDash(stats.era)}</span>
    </div>`;
  };
  const probables = game.status.normalized === "SCHEDULED"
    ? `<aside class="game-probables detail"><h3>${t("game.probables")}</h3>${probableLine("away")}${probableLine("home")}</aside>`
    : "";
  const sidePanel = decisions || probables;
  const decisionHeading = decisions
    ? `<span class="game-summary-side-title">${t("game.decisions")}</span>`
    : "";
  return `<div class="card mb-4" id="game-linescore"><div class="card-header fw-bold game-summary-heading${decisions ? " has-decisions" : ""}"><span>${t("game.linescore")}</span>${decisionHeading}</div>
    <div class="game-summary-grid${sidePanel ? "" : " no-decisions"}"><div class="table-responsive"><table class="table table-sm text-center mb-0 linescore-table" style="--inning-count:${inningCount}">
      <thead><tr><th>Team</th>${headers}<th>R</th><th>H</th><th>E</th></tr></thead><tbody>${row("away")}${row("home")}</tbody>
    </table></div>${sidePanel}</div>
  </div>`;
}

function statTable(teamBox, type) {
  const playerName = (row) => row.player_id
    ? `<a href="/players/${row.player_id}" data-link class="boxscore-player-link">${escapeHtml(row.name)}</a>`
    : escapeHtml(row.name);
  if (type === "batters") {
    const rows = teamBox.batters || [];
    const t = teamBox.batting_totals || {};
    return `<h3 class="boxscore-section-title">Batters</h3><div class="table-responsive"><table class="table table-sm align-middle stat-line-table batting-table mb-0">
      <colgroup><col class="stat-pos"><col class="stat-player"><col span="8" class="stat-number"></colgroup>
      <thead><tr><th>Pos</th><th>Player</th><th>AB</th><th>R</th><th>H</th><th>RBI</th><th>BB</th><th>K</th><th>AVG</th><th>OPS</th></tr></thead><tbody>
      ${rows.length ? rows.map((r) => `<tr><td class="text-secondary">${escapeHtml(r.position)}</td><th>${playerName(r)}</th><td>${r.at_bats}</td><td>${r.runs}</td><td>${r.hits}</td><td>${r.rbi}</td><td>${r.walks}</td><td>${r.strikeouts}</td><td>${valueOrDash(r.avg)}</td><td>${valueOrDash(r.ops)}</td></tr>`).join("") : `<tr><td colspan="10" class="text-secondary py-3">${state.language === "ja" ? "打撃データなし" : "暂无击球数据"}</td></tr>`}
      ${rows.length ? `<tr class="totals-row"><td></td><th>Totals</th><td>${valueOrDash(t.atBats)}</td><td>${valueOrDash(t.runs)}</td><td>${valueOrDash(t.hits)}</td><td>${valueOrDash(t.rbi)}</td><td>${valueOrDash(t.baseOnBalls)}</td><td>${valueOrDash(t.strikeOuts)}</td><td>—</td><td>—</td></tr>` : ""}
      </tbody></table></div>`;
  }
  const rows = teamBox.pitchers || [];
  const t = teamBox.pitching_totals || {};
  return `<h3 class="boxscore-section-title pitching-title">Pitchers</h3><div class="table-responsive"><table class="table table-sm align-middle stat-line-table pitching-table mb-0">
    <colgroup><col class="stat-player"><col span="8" class="stat-number"></colgroup>
    <thead><tr><th>Player</th><th>IP</th><th>H</th><th>R</th><th>ER</th><th>BB</th><th>K</th><th>HR</th><th>ERA</th></tr></thead><tbody>
    ${rows.length ? rows.map((r) => `<tr><th>${playerName(r)}${r.note ? ` <small class="pitcher-note">${escapeHtml(r.note)}</small>` : ""}</th><td>${valueOrDash(r.innings)}</td><td>${r.hits}</td><td>${r.runs}</td><td>${r.earned_runs}</td><td>${r.walks}</td><td>${r.strikeouts}</td><td>${r.home_runs}</td><td>${valueOrDash(r.era)}</td></tr>`).join("") : `<tr><td colspan="9" class="text-secondary py-3">${state.language === "ja" ? "投球データなし" : "暂无投球数据"}</td></tr>`}
    ${rows.length ? `<tr class="totals-row"><th>Totals</th><td>${valueOrDash(t.inningsPitched)}</td><td>${valueOrDash(t.hits)}</td><td>${valueOrDash(t.runs)}</td><td>${valueOrDash(t.earnedRuns)}</td><td>${valueOrDash(t.baseOnBalls)}</td><td>${valueOrDash(t.strikeOuts)}</td><td>${valueOrDash(t.homeRuns)}</td><td>—</td></tr>` : ""}
    </tbody></table></div>`;
}

function boxscoreSection(game, boxscore) {
  if (!boxscore || !Object.keys(boxscore).length) return "";
  return `<section class="card game-boxscore mb-4" id="game-boxscore"><div class="card-header boxscore-heading"><strong>${t("game.boxscore")}</strong>
    <ul class="nav nav-pills boxscore-tabs" role="tablist">${["away", "home"].map((side, index) => `<li class="nav-item" role="presentation"><button class="nav-link${index === 0 ? " active" : ""}" data-bs-toggle="tab" data-bs-target="#${side}-boxscore" type="button" role="tab">${escapeHtml(game[side].team.abbreviation)}</button></li>`).join("")}</ul>
  </div><div class="tab-content">${["away", "home"].map((side, index) => `<div class="tab-pane fade${index === 0 ? " show active" : ""}" id="${side}-boxscore" role="tabpanel" tabindex="0">
    <div class="boxscore-team-heading"><a href="/teams/${game[side].team.mlb_team_id}" data-link class="team-link">${logo(game[side].team, 32)}<strong>${escapeHtml(game[side].team.name)}</strong></a></div>
    ${statTable(boxscore[side] || {}, "batters")}${statTable(boxscore[side] || {}, "pitchers")}
  </div>`).join("")}</div></section>`;
}

function activeRosterPlayer(entry) {
  if (!entry) return `<div class="game-active-roster-player is-empty" aria-hidden="true"></div>`;
  const details = rosterStatLine(entry);
  return `<a class="game-active-roster-player" href="/players/${entry.player.mlb_player_id}" data-link>
    <strong>${escapeHtml(entry.player.full_name)}</strong>
    <span class="team-roster-player-stats ${details.modifier}">${details.html}</span>
  </a>`;
}

function activeRosterSection(activeRosters) {
  if (!activeRosters?.away || !activeRosters?.home) return "";
  const categories = [
    ["pitchers", "投手"],
    ["catchers", "捕手"],
    ["infielders", "内野手"],
    ["outfielders", "外野手"],
  ];
  const categorySection = ([key, label]) => {
    const away = activeRosters.away.groups?.[key] || [];
    const home = activeRosters.home.groups?.[key] || [];
    const rowCount = Math.max(away.length, home.length);
    if (!rowCount) return "";
    return `<section class="game-active-roster-category"><h4>${label}</h4><div class="game-active-roster-grid">${Array.from({ length: rowCount }, (_, index) =>
      `${activeRosterPlayer(away[index])}${activeRosterPlayer(home[index])}`
    ).join("")}</div></section>`;
  };
  const teamHeading = (side) => {
    const roster = activeRosters[side];
    return `<div class="game-active-roster-team"><a href="/teams/${roster.team.mlb_team_id}" data-link>${logo(roster.team, 30)}<strong>${escapeHtml(roster.team.name)}</strong></a><span>${roster.count} 人</span></div>`;
  };
  return `<section class="card game-active-roster mb-4" id="game-active-roster">
    <div class="card-header fw-bold">Active Roster</div>
    <div class="game-active-roster-team-grid">${teamHeading("away")}${teamHeading("home")}</div>
    ${categories.map(categorySection).join("")}
  </section>`;
}

function analysisPanels(analyses) {
  const chineseLabels = {
    summary: "比赛概述",
    turning_point: "比赛转折点",
    key_players: "关键球员",
    home_team_review: "主队回顾",
    away_team_review: "客队回顾",
    overview: "比赛展望",
    starter_matchup: "先发对决",
    team_form: "近期状态",
    outlook: "比赛展望",
    current_situation: "当前赛况",
    turning_points: "走势转折",
    bullpen_outlook: "牛棚与走势判断",
    scoring_progression: "得分进程",
    batting_highlights: "打击亮点",
    pitching_highlights: "投手表现",
    watch_points: "后续看点",
    data_limitations: "数据限制",
    season_review: "本赛季表现",
    recent_form: "近期表现",
  };
  const japaneseLabels = {
    summary: "試合概要", turning_point: "試合の転機", turning_points: "流れを変えた場面", key_players: "キープレーヤー",
    home_team_review: "ホームチーム回顧", away_team_review: "ビジターチーム回顧", overview: "展望",
    starter_matchup: "先発投手の比較", team_form: "直近の状態", outlook: "今後の見通し",
    current_situation: "現在の状況", bullpen_outlook: "ブルペンと試合展開の予測", scoring_progression: "得点経過",
    batting_highlights: "打撃ハイライト", pitching_highlights: "投手成績", watch_points: "注目点",
    data_limitations: "データ上の制約", season_review: "今季の評価", recent_form: "直近の内容",
  };
  const labels = state.language === "ja" ? japaneseLabels : chineseLabels;
  const renderValue = (value) => {
    if (typeof value === "string") return `<p>${escapeHtml(value)}</p>`;
    if (Array.isArray(value)) {
      return `<ul>${value.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }
    if (value && typeof value === "object") {
      return `<div class="analysis-subsections">${Object.entries(value).map(([key, item]) =>
        `<div><h4>${escapeHtml(key.replaceAll("_", " "))}</h4>${renderValue(item)}</div>`
      ).join("")}</div>`;
    }
    return `<p>${escapeHtml(value ?? "—")}</p>`;
  };
  return analyses.map((analysis) => `<div class="analysis-panel mb-3">${
    Object.entries(analysis.content).map(([key, value]) => `<h3 class="h6">${escapeHtml(labels[key] || key.replaceAll("_", " "))}</h3>${renderValue(value)}`).join("")
  }<small class="text-secondary">${escapeHtml(analysis.model_name)} · ${fullDateTime(analysis.created_at)}</small></div>`).join("");
}

async function renderGameDetail(gamePk) {
  try {
    const response = await api(`/api/games/${gamePk}?lang=${state.language}`);
    const { game, linescore, boxscore, active_rosters: activeRosters, analyses, calendar } = response.data;
    setTitle(`${game.away.team.abbreviation} @ ${game.home.team.abbreviation}`);
    const standingLine = (side) => {
      const standing = game[side].standing;
      return standing ? `<p class="team-standing-line">${standing.wins}–${standing.losses} · ${escapeHtml(game[side].team.division)}${standing.division_rank ? ` ${rankLabel(standing.division_rank)}` : ""}</p>` : "";
    };
    const calendarUnavailable = ["FINAL", "POSTPONED", "CANCELLED", "SUSPENDED"].includes(game.status.normalized);
    const calendarAdded = Boolean(calendar?.added);
    const isPregameAnalysis = !["FINAL", "LIVE"].includes(game.status.normalized);
    const pregameAnalysisDisabled = isPregameAnalysis && (
      !game.away.probable_pitcher || !game.home.probable_pitcher
    );
    const analysisButtonText = pregameAnalysisDisabled
      ? t("ai.waitProbables")
      : analyses.length ? t("ai.update") : t("ai.generate");
    const analysisButtonClass = pregameAnalysisDisabled ? "btn-secondary" : "btn-danger";
    app.innerHTML = `<section class="scoreboard mb-4" data-game-pk="${game.game_pk}" data-live="${game.status.normalized === "LIVE"}">
      <div class="score-team"><a href="/teams/${game.away.team.mlb_team_id}" data-link class="score-team-link">${logo(game.away.team, 76)}<h2>${escapeHtml(game.away.team.name)}</h2></a>${standingLine("away")}<strong id="away-score">${valueOrDash(game.away.score)}</strong></div>
      <div class="score-meta">${statusBadge(game)}<p class="mt-3 mb-1">${fullDateTime(game.start_time_utc)} JST</p><small class="score-venue">${escapeHtml(game.venue_name || "球场待定")}</small>
        <button class="calendar-game-button${calendarAdded ? " is-added" : ""}" id="calendar-game-button" ${calendarAdded || calendarUnavailable ? "disabled" : ""}>${calendarAdded ? t("game.addedCalendar") : t("game.addCalendar")}</button>
        <div id="inning" class="live-line mt-2">${game.status.normalized === "LIVE" ? inningLabel(game.status.current_inning, game.status.inning_half) : ""}</div></div>
      <div class="score-team"><a href="/teams/${game.home.team.mlb_team_id}" data-link class="score-team-link">${logo(game.home.team, 76)}<h2>${escapeHtml(game.home.team.name)}</h2></a>${standingLine("home")}<strong id="home-score">${valueOrDash(game.home.score)}</strong></div>
    </section>
    ${linescoreTable(game, linescore)}
    ${boxscoreSection(game, boxscore)}
    ${activeRosterSection(activeRosters)}
    <div class="card"><div class="card-header fw-bold">${game.status.normalized === "FINAL" ? t("game.aiFinal") : game.status.normalized === "LIVE" ? t("game.aiLive") : t("game.aiPregame")}</div><div class="card-body">
      <div id="analyses">${analysisPanels(analyses)}</div><button class="btn ${analysisButtonClass}" id="analysis-button" ${pregameAnalysisDisabled ? "disabled" : ""}>${analysisButtonText}</button>
    </div></div>`;
    const analysisButton = document.querySelector("#analysis-button");
    if (!pregameAnalysisDisabled) analysisButton.addEventListener("click", async () => {
      const button = document.querySelector("#analysis-button");
      let coolingDown = false;
      button.disabled = true;
      try {
        const result = await api(`/api/games/${gamePk}/analyses`, { method: "POST", body: { language: state.language } });
        notice(result.meta?.cached ? t("ai.cached") : t("ai.generated"));
        await renderGameDetail(gamePk);
      } catch (error) {
        if (error.code === "AI_RATE_LIMITED") {
          coolingDown = true;
          startAnalysisCooldown(button, error.retryAfter);
        } else {
          notice(error.message, "warning");
        }
      } finally {
        if (!coolingDown) button.disabled = false;
      }
    });
    const calendarButton = document.querySelector("#calendar-game-button");
    const startCalendarAuthorization = async () => {
      try {
        const result = await api("/api/calendar/authorization", { method: "POST", body: {} });
        location.href = result.data.authorization_url;
      } catch (error) {
        notice(error.message, "warning");
      }
    };
    if (!calendarAdded && !calendarUnavailable) {
      calendarButton.addEventListener("click", async () => {
        calendarButton.disabled = true;
        if (!calendar?.connected) {
          await startCalendarAuthorization();
          calendarButton.disabled = false;
          return;
        }
        try {
          await api("/api/calendar/events", { method: "POST", body: { game_pk: Number(gamePk) } });
          calendarButton.textContent = t("game.addedCalendar");
          calendarButton.classList.add("is-added");
          calendarButton.disabled = true;
        } catch (error) {
          if (error.code === "CALENDAR_ERROR") {
            await startCalendarAuthorization();
          } else {
            notice(error.message, "warning");
          }
          calendarButton.disabled = false;
        }
      });
    }
    if (game.status.normalized === "LIVE") startLiveRefresh(gamePk, game);
  } catch (error) {
    if (!requireLogin(error)) throw error;
  }
}

function startLiveRefresh(gamePk, game) {
  clearInterval(liveTimer);
  liveTimer = setInterval(async () => {
    try {
      const { data } = await api(`/api/games/${gamePk}/status`);
      document.querySelector("#away-score").textContent = data.away_score ?? "—";
      document.querySelector("#home-score").textContent = data.home_score ?? "—";
      document.querySelector("#inning").textContent = data.status === "LIVE"
        ? inningLabel(data.current_inning, data.inning_half)
        : data.detailed_status;
      if (data.status !== "LIVE") {
        await renderGameDetail(gamePk);
        return;
      }
      game.away.score = data.away_score;
      game.home.score = data.home_score;
      game.status.current_inning = data.current_inning;
      game.status.inning_half = data.inning_half;
      const currentLinescore = document.querySelector("#game-linescore");
      if (currentLinescore) currentLinescore.outerHTML = linescoreTable(game, data.linescore);
      const currentBoxscore = document.querySelector("#game-boxscore");
      const activeTarget = currentBoxscore
        ?.querySelector(".boxscore-tabs .nav-link.active")
        ?.getAttribute("data-bs-target");
      const boxscoreHtml = boxscoreSection(game, data.boxscore);
      if (currentBoxscore && boxscoreHtml) {
        currentBoxscore.outerHTML = boxscoreHtml;
      } else if (!currentBoxscore && boxscoreHtml) {
        document.querySelector("#game-linescore")?.insertAdjacentHTML("afterend", boxscoreHtml);
      }
      if (activeTarget === "#home-boxscore") {
        const homeTab = document.querySelector('[data-bs-target="#home-boxscore"]');
        if (homeTab) bootstrap.Tab.getOrCreateInstance(homeTab).show();
      }
      const currentRoster = document.querySelector("#game-active-roster");
      const rosterHtml = activeRosterSection(data.active_rosters);
      if (currentRoster && rosterHtml) currentRoster.outerHTML = rosterHtml;
    } catch (error) {
      console.warn("Live game refresh failed; retaining current data.", error);
    }
  }, 30000);
}

function authForm(mode) {
  const login = mode === "login";
  setTitle(login ? "登录" : "注册");
  app.innerHTML = `<div class="card auth-card mx-auto"><div class="card-body p-4 p-md-5">
    <p class="eyebrow text-danger mb-2">${login ? "WELCOME BACK" : "CREATE ACCOUNT"}</p><h1 class="h3 mb-4">${login ? "登录" : "注册"}</h1>
    <div id="auth-error"></div><form id="auth-form">
      <div class="mb-3"><label class="form-label" for="email">邮箱</label><input class="form-control" id="email" type="email" autocomplete="email" required></div>
      <div class="mb-3"><label class="form-label" for="password">密码</label><input class="form-control" id="password" type="password" autocomplete="${login ? "current-password" : "new-password"}" minlength="10" required></div>
      <button class="btn btn-danger w-100">${login ? "登录" : "创建账号"}</button>
    </form>
    <div class="divider">或</div><a class="btn btn-outline-dark w-100" href="${API_BASE_URL}/api/auth/google">使用 Google 登录</a>
    <p class="text-secondary small mt-4 mb-0">${login ? `还没有账号？<a href="/register" data-link>注册</a>` : `已有账号？<a href="/login" data-link>登录</a>`}</p>
  </div></div>`;
  document.querySelector("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.querySelector("#email").value;
    const password = document.querySelector("#password").value;
    try {
      const response = await api(`/api/auth/${login ? "login" : "register"}`, {
        method: "POST",
        body: { email, password },
      });
      const sessionResponse = await api("/api/auth/session");
      state.session = sessionResponse.data;
      renderNav();
      const next = new URLSearchParams(location.search).get("next") || "/";
      navigate(next);
    } catch (error) {
      document.querySelector("#auth-error").innerHTML = `<div class="alert alert-danger">${escapeHtml(error.message)}</div>`;
    }
  });
}

function renderNotFound() {
  setTitle("页面不存在");
  app.innerHTML = `<div class="empty-state"><h1 class="h3">404</h1><p>找不到该页面。</p><a href="/" data-link class="btn btn-dark">返回首页</a></div>`;
}

async function route() {
  clearInterval(liveTimer);
  liveTimer = null;
  loading();
  const path = location.pathname;
  try {
    if (path === "/") await renderHome();
    else if (path === "/schedule") await renderSchedule();
    else if (path === "/standings") await renderStandings();
    else if (path === "/teams") await renderTeams();
    else if (/^\/teams\/\d+$/.test(path)) await renderTeamDetail(path.split("/")[2]);
    else if (path === "/players") await renderPlayers();
    else if (/^\/players\/\d+$/.test(path)) await renderPlayerDetail(path.split("/")[2]);
    else if (/^\/games\/\d+$/.test(path)) await renderGameDetail(path.split("/")[2]);
    else if (path === "/login") authForm("login");
    else if (path === "/register") authForm("register");
    else renderNotFound();
  } catch (error) {
    console.error(error);
    app.innerHTML = `<div class="empty-state"><h1 class="h4">暂时无法显示此页面</h1><p>${escapeHtml(error.message)}</p><button class="btn btn-dark" id="retry-button">重试</button></div>`;
    document.querySelector("#retry-button").addEventListener("click", route);
  }
}

function navigate(url) {
  history.pushState({}, "", url);
  route();
  window.scrollTo({ top: 0, behavior: "instant" });
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-link]");
  if (!link || link.origin !== location.origin) return;
  event.preventDefault();
  navigate(link.pathname + link.search);
});
window.addEventListener("popstate", route);

async function bootstrap() {
  applyStaticTranslations();
  try {
    const [sessionResponse, metaResponse] = await Promise.all([
      api("/api/auth/session"),
      api("/api/meta"),
    ]);
    state.session = sessionResponse.data;
    state.meta = metaResponse.data;
    renderNav();
    updateFooter();
  } catch {
    state.session = { authenticated: false, user: null };
    renderNav();
  }
  await route();
}

bootstrap();
