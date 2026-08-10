# MLB Dugout Web Service

以 MLB 数据为主题、严格采用 Client/Server 分离架构的 Web Service 最终项目。Vanilla JavaScript 客户端只调用 Flask REST API；API 只读取 PostgreSQL。MLB Stats API 仅由 CLI 同步服务访问，因此外部 API 暂时不可用时，最近一次成功同步的数据仍可展示。

## 已实现

### P0

- Flask Application Factory、Blueprint、SQLAlchemy、Flask-Migrate
- PostgreSQL + Docker Compose + Gunicorn + Python 标准库静态客户端 + `/healthz`
- Flask-CORS 只允许受信任的 Client origin，并支持 JWT Cookie 凭据
- 15 张领域表、MLB 原始 ID 唯一约束、幂等 upsert
- MLBClient：连接/读取超时、429/5xx 重试、指数退避、User-Agent、JSON 异常处理
- 球队、赛程、排名、roster、球队/球员统计、live feed 同步 CLI
- 日本时间今日全部比赛、六赛区简表
- 月份/球队赛程筛选、详细排名、30 队分组、球员选择入口
- 比赛状态：Scheduled、Live、Final、Delayed、Postponed、Suspended、Cancelled、Unknown
- 邮箱注册、登录、注销；JWT 保存于 HttpOnly Cookie；Cookie CSRF
- 受保护 API 返回标准 JSON 401，客户端负责登录跳转
- 真实裁剪 MLB fixture 和默认离线 pytest

### P1

- 球队详情、roster、球队赛季统计
- 球员打击/投球详情；投球局数以出局数整数可靠存储
- 比赛详情的赛前/进行中/赛后三种模式与 REST JSON 局部刷新
- Google OIDC 登录（仅 `openid email profile`）
- 独立 Google Calendar OAuth；Fernet 加密 Token、刷新、撤销处理、重复事件防护
- Gemini 赛前/赛中/赛后分析；环境变量模型、超时/重试、source hash 缓存、友好降级
- 球员最近 10 次出场数据与按需 Gemini 赛季表现分析
- 中文/日文界面切换；AI 输出按语言分别缓存
- Azure App Service 部署说明

## 未实现 / Future Work（原始需求清单）

- 球员历史赛季、姓名搜索
- 对其他 29 队战绩
- 球员联盟平均值、队内/联盟排名、百分位及复杂可视化
- 赛前双方近 10 场完整得失分、赛季交锋的独立可视化
- Live 当前打者/投手/投球数、逐事件与换人记录的独立时间线
- Final 关键得分事件的独立列表（当前 boxscore 与 AI 总结已实现）
- 数据超过阈值时的显式“可能过期”横幅（当前只显示最后更新时间）
- Statcast 全量逐球、球种/球速/转速/位移（明确不在本项目范围）

## 架构

```text
MLB Stats API
  → MLBClient
  → MLBSyncService / Flask CLI
  → PostgreSQL
  → Flask REST API / SQLAlchemy（公开 HTTPS :2028，独立 api 容器）
  ⇄ Flask-CORS（允许 https://localhost:2027，携带 Cookie）
  → HTML + Bootstrap + Vanilla JavaScript（HTTPS :2027，独立 client 容器）
```

客户端不包含数据库访问代码、MLB 原始 JSON 解析或业务逻辑。Flask 不渲染 HTML，也不提供 Jinja 页面；客户端直接跨 origin 调用 Flask API，所有浏览器数据均来自服务器简化包装后的 JSON resource。Google 与 Gemini 故障只影响对应操作，不影响 MLB 数据页面。

### REST API

| Method | Endpoint | 用途 | 权限 |
|---|---|---|---|
| GET | `/api/games?date=YYYY-MM-DD` | 某日比赛卡数据 | Public |
| GET | `/api/games?month=YYYY-MM&team=ID` | 月份/球队日程 | Public |
| GET | `/api/games/{gamePk}` | 完整比赛详情、局分、责任投手、boxscore、AI 结果 | User |
| GET | `/api/games/{gamePk}/status` | 比赛状态局部刷新 | User |
| POST | `/api/games/{gamePk}/analyses` | 生成或读取 AI 分析 | User |
| GET | `/api/standings` | 六赛区排名及球队赛季数据 | Public |
| GET | `/api/teams` | 30 支球队 | Public |
| GET | `/api/teams/{mlbTeamId}` | 球队详情 | User |
| GET | `/api/teams/{mlbTeamId}/roster` | 球队 roster | Public |
| GET | `/api/players/{mlbPlayerId}?lang=zh|ja` | 球员赛季数据、最近 10 场出场与 AI 结果 | User |
| POST | `/api/players/{mlbPlayerId}/analyses` | 按请求语言生成或读取球员 AI 分析 | User |
| GET/POST | `/api/auth/*` | Session、注册、登录、注销、Google OIDC | Mixed |
| POST | `/api/calendar/authorization` | 开始 Calendar OAuth | User |
| POST | `/api/calendar/events` | 添加比赛 | User |

统一响应使用 `{"data": ...}`；错误使用 `{"error": {"code": "...", "message": "..."}}`。API 不会原样返回 MLB Stats API 的 live feed 或 boxscore。

## 本地 Docker 启动

要求 Docker Desktop / Docker Engine 与 Compose。

```bash
cp .env.example .env
# 编辑 .env，至少替换 SECRET_KEY 和 JWT_SECRET_KEY
docker compose up --build
```

打开客户端 `https://localhost:2027`。REST API 位于 `https://localhost:2028/api`；API 容器内部的 Gunicorn 仍监听 `2027`，Docker 只把它映射到主机端口 `2028`，从而形成真实的跨 origin C/S 调用。

本地容器启动时会自动生成一张只用于开发的共享自签名证书，Client 与 API 都使用这张证书。浏览器第一次访问会显示证书不受信任警告；确认地址为 localhost 后可以继续访问。生产环境必须使用受信任 CA 证书或由 Azure App Service 终止 TLS。

入口脚本会等待 PostgreSQL 并自动执行 `flask db upgrade`。手动迁移：

```bash
docker compose exec api flask --app wsgi:app db upgrade
```

停止容器（保留数据库 volume）：

```bash
docker compose down
```

## 初始化与同步

首次完整同步：

```bash
docker compose exec api flask --app wsgi:app sync-all --season 2026
```

分步同步：

```bash
docker compose exec api flask --app wsgi:app sync-teams
docker compose exec api flask --app wsgi:app sync-schedule --start 2026-03-25 --end 2026-09-27
docker compose exec api flask --app wsgi:app sync-standings --season 2026
docker compose exec api flask --app wsgi:app sync-rosters --season 2026
docker compose exec api flask --app wsgi:app sync-team-stats --season 2026
docker compose exec api flask --app wsgi:app sync-player-stats --season 2026
docker compose exec api flask --app wsgi:app sync-live-games
docker compose exec api flask --app wsgi:app sync-current-games --lookback-days 1
```

`sync-current-games` 是给 Azure 外部调度器调用的一次性命令：它先刷新 JST 最近赛程，使 Scheduled 状态能够推进为 Live/Final，再获取进行中比赛的 live feed。它不会在应用内启动定时器。

`sync-player-stats` 会遍历当前 roster，初次运行时间最长；单个球员失败只记录日志并继续。

使用独立的 `sync-worker` sidecar 执行生产自动同步，不在 Flask Web
进程内运行定时循环。`bootstrap-sync` 完成全量初始化并写入数据库标记后，
worker 才会开始：

| 数据 | 当前频率 |
|---|---|
| 当前比赛与最近赛程 | 5 分钟（`sync-current-games`） |
| 排名 | 12 小时 |
| 球队赛季统计 | 12 小时 |
| roster | 12 小时 |
| 球员赛季统计 | 12 小时 |
| 已结束比赛 | 确认 final 后停止高频更新 |
| 历史赛季 | 首次获取后长期保存 |

容器内脚本：

```bash
/app/scripts/bootstrap_sync.sh
/app/scripts/sync_worker.sh
```

API 主容器负责执行 Alembic。两个同步 sidecar 设置
`SKIP_DB_MIGRATIONS=1`，避免多个容器竞争迁移记录。

## 环境变量

| 变量 | 必需 | 说明 |
|---|---:|---|
| `FLASK_ENV` | 是 | `development` 或生产环境标识 |
| `SECRET_KEY` | 是 | Flask session 随机密钥 |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥，至少 32 字节 |
| `JWT_COOKIE_SAMESITE` | 是 | 跨 origin Cookie 使用 `None`，且必须同时保持 Secure |
| `SESSION_COOKIE_SAMESITE` | 是 | OAuth session 跨 origin 使用 `None` |
| `DATABASE_URL` | 是 | `postgresql+psycopg://...`；也兼容 Azure 提供的 `postgresql://` |
| `MLB_SEASON` | 是 | 默认展示赛季，如 `2026` |
| `APP_TIMEZONE` | 是 | 默认 `Asia/Tokyo` |
| `MLB_SYNC_START` | bootstrap | 全量赛程同步开始日期 |
| `MLB_SYNC_END` | bootstrap | 全量赛程同步结束日期 |
| `SKIP_DB_MIGRATIONS` | sidecar | API 主容器为 `0`；同步 sidecar 为 `1` |
| `SYNC_CURRENT_INTERVAL_SECONDS` | worker | 当前比赛同步间隔，默认 `300` |
| `SYNC_DAILY_INTERVAL_SECONDS` | worker | 排名、统计与 roster 同步间隔，默认 `43200` |
| `SYNC_WORKER_POLL_SECONDS` | worker | worker 调度检查间隔，默认 `30` |
| `SYNC_WORKER_STARTUP_GRACE_SECONDS` | worker | 等待 bootstrap 写入 started 标记的启动缓冲，默认 `60` |
| `GEMINI_API_KEY` | AI | Gemini API Key |
| `GEMINI_MODEL` | AI | Gemini 模型名；代码不硬编码 Preview 模型 |
| `GOOGLE_CLIENT_ID` | Google | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google | Google OAuth Client Secret |
| `GOOGLE_LOGIN_REDIRECT_URI` | Google | OIDC 回调，默认 API 的 `/api/auth/google/callback` |
| `GOOGLE_CALENDAR_REDIRECT_URI` | Calendar | Calendar 回调，默认 API 的 `/api/calendar/callback` |
| `TOKEN_ENCRYPTION_KEY` | Calendar | Fernet 对称密钥 |
| `BASE_URL` | Calendar | API 公开根 URL；本地为 `https://localhost:2028` |
| `CLIENT_URL` | 是 | 客户端公开根 URL；本地为 `https://localhost:2027` |
| `CORS_ORIGINS` | 是 | 允许调用 API 的客户端 origin，多个值用逗号分隔 |
| `API_BASE_URL` | Client | 浏览器调用的 API 根 URL；本地为 `https://localhost:2028` |
| `TLS_MODE` | 是 | 本地 Docker 使用 `direct`；Azure App Service 使用 `proxy` |
| `TLS_CERT_FILE` | 本地 HTTPS | 开发证书路径，默认 `/tmp/mlb-dugout.crt` |
| `TLS_KEY_FILE` | 本地 HTTPS | 开发私钥路径，默认 `/tmp/mlb-dugout.key` |

生成 Fernet Key：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

任何真实秘密都不能提交到 Git。

## Google 配置

在 Google Cloud Console 创建 Web OAuth Client，并添加两条 Redirect URI：

- `https://localhost:2028/api/auth/google/callback`
- `https://localhost:2028/api/calendar/callback`

登录只请求身份 scope。用户登录后主动点击“连接 Google Calendar”才请求 `calendar.events`。已有邮箱密码账号不会只凭相同邮箱自动与新 Google subject 合并。

## Gemini

设置 `GEMINI_API_KEY` 和 `GEMINI_MODEL`。AI 只接收数据库整理后的结构化输入：

- Scheduled → AI 赛前展望
- Live → 手动 AI 比赛中分析
- Final → AI 赛后总结
- Player → 点击生成后分析赛季成绩与最近出场表现

相同输入和语言先按 SHA-256 source hash 查询 `ai_analyses`；中文与日文分析使用独立缓存。Gemini 未配置、超时、限流或响应无效时，页面保持可用并提示重试。

## 测试

默认测试不访问 MLB、Google 或 Gemini：

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
```

覆盖状态映射、UTC/JST、JST 日期边界、局数转换、API 重试配置、upsert 幂等、排名解析、REST resource 包装、权限、注册登录、JWT Cookie、客户端/服务器容器边界、OAuth state、Calendar 去重、AI 缓存与 AI 未配置降级。

手动外部 smoke test：

```bash
python scripts/smoke_external_services.py
python scripts/smoke_external_services.py --google
# 下面一次最小请求可能计费
python scripts/smoke_external_services.py --gemini
```

探索真实 MLB 数据：

```bash
python scripts/explore_mlb_api.py schedule --date 2026-07-21 --output /tmp/schedule.json
python scripts/explore_mlb_api.py live --game-pk 822786 --output /tmp/live.json
```

## 时间规则

数据库保存 timezone-aware UTC，并保存/显示 JST。首页“今日”以 `Asia/Tokyo` 的 00:00–23:59 为边界，再转换为 UTC 查询；不会把日本日期直接当作 MLB 官方日期。测试 fixture 中，`2026-07-19T16:15:00Z` 正确归入日本时间 `2026-07-20`。

## 已知风险

- Google OIDC、Calendar 和 Gemini 的真实端到端调用需要你自己的凭据，本仓库只完成离线测试和降级测试。
- 初次全 roster 球员统计同步请求较多；已节流并按球员隔离失败，但仍可能受 MLB 限流影响。
- 初始迁移从当前 SQLAlchemy metadata 创建 15 张表；发布后新增字段应继续生成新的显式 Alembic revision，不要修改 `0001_initial`。
- MLB API 为公开但非本项目控制的外部服务，字段变化时先运行探索脚本并更新 fixture/解析测试。

## 演示顺序

1. 首页：今日比赛、状态标签、六赛区简表
2. 日程：切换 `2026-07` 与球队
3. 排名：六赛区详细数据与 run differential
4. 球队：30 队分组、Logo fallback
5. 访客点击详情 → API 401 → 客户端登录跳转
6. 注册/登录 → 比赛详情、球队详情、球员详情
7. 手动 AI 分析：未配置时展示友好降级；配置后展示缓存
8. Google Calendar：说明独立授权、未来比赛与重复防护

详细实施记录见 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)，Azure 步骤见 [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md)。
