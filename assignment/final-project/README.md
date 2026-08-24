# MLB Dugout

MLB Dugout is a full-stack web service for exploring Major League Baseball games, standings, teams, rosters, and player performance. It uses a strictly separated client/server architecture: a framework-free JavaScript client consumes a Flask REST API, while the API reads application data from PostgreSQL.

The server periodically synchronizes normalized data from the MLB Stats API. Because the browser never calls MLB directly, the application can continue serving the most recently synchronized data when the upstream service is temporarily unavailable.

## Live Deployment

| Service | URL |
|---|---|
| Web client | [Open MLB Dugout](https://kcgi-mlb-dugout-client-b3bgaqagafardzcu.japaneast-01.azurewebsites.net/) |
| REST API | [API base URL](https://kcgi-mlb-dugout-api-ddgdhjcpcah0augw.japaneast-01.azurewebsites.net/) |
| API health check | [View health status](https://kcgi-mlb-dugout-api-ddgdhjcpcah0augw.japaneast-01.azurewebsites.net/api/health) |

Both services are deployed independently on Microsoft Azure App Service in the Japan East region.

## Highlights

- Daily and monthly MLB schedules displayed in Japan Standard Time
- Live, scheduled, final, delayed, postponed, suspended, and cancelled game states
- Inning-by-inning linescores, decisions, box scores, and active rosters
- Division standings for all six MLB divisions
- Team pages with weekly and monthly calendars and complete roster information
- Player pages with season statistics and up to 10 recent appearances
- Email/password authentication and Google OpenID Connect sign-in
- Google Calendar integration with duplicate-event protection
- On-demand Gemini analysis for pregame, live, final, and player contexts
- Chinese and Japanese user interfaces, including language-aware AI output
- Manual synchronization from the client and automated production synchronization
- Responsive, framework-free client built with HTML, CSS, and Vanilla JavaScript

## Architecture

```text
                         synchronization only
MLB Stats API ─────────────────────────────────────┐
                                                   ▼
                                      MLBClient / Flask CLI
                                                   │
                                                   ▼
Browser ── HTTPS ──► Static JavaScript Client ──► Flask REST API
                          Azure App Service       Azure App Service
                                                        │
                                                        ▼
                                                   PostgreSQL

Google OAuth / Calendar ◄──────────────────────── Flask REST API
Gemini API              ◄──────────────────────── Flask REST API
```

The client and API are deployed as separate applications and communicate across origins through credential-aware CORS. Flask does not render HTML or expose Jinja pages. The client contains no database access, MLB payload parsing, or server-side business logic; it receives simplified JSON resources designed specifically for the UI.

MLB, Google, and Gemini integrations are isolated behind server-side services. An outage in Google or Gemini affects only the related optional action, not the core MLB pages.

## Technology Stack

| Layer | Technologies |
|---|---|
| Client | HTML5, CSS3, Vanilla JavaScript, Bootstrap |
| API | Python, Flask, Flask-CORS, Flask-JWT-Extended |
| Data | PostgreSQL, SQLAlchemy, Flask-Migrate, Alembic |
| Authentication | JWT in HttpOnly cookies, CSRF protection, Google OIDC |
| External services | MLB Stats API, Google Calendar API, Gemini API |
| Runtime | Gunicorn, Docker, Docker Compose |
| Production | Microsoft Azure App Service with container sidecars |
| Testing | pytest with offline MLB fixtures |

## Data Flow and Synchronization

MLB Stats API responses are parsed and normalized by the server before being stored. The browser never receives the original upstream live-feed or box-score payloads.

```text
MLB Stats API
  → resilient MLB client
  → synchronization service
  → idempotent database upserts
  → PostgreSQL
  → REST serializers
  → client-specific JSON
```

The MLB client applies connection and read timeouts, retries for rate limits and server errors, exponential backoff, response validation, and a project-specific User-Agent. MLB identifiers are protected by unique constraints, and repeated synchronization uses idempotent upserts.

Production synchronization runs in a worker sidecar rather than in the Flask web process:

| Data | Frequency |
|---|---:|
| Current games and recent schedules | Every 5 minutes |
| Standings | Every 12 hours |
| Team season statistics | Every 12 hours |
| Active and 40-man rosters | Every 12 hours |
| Player season statistics | Every 12 hours |

Completed games stop receiving high-frequency live updates. Historical data remains available from PostgreSQL after its initial synchronization.

## REST API

Successful responses use `{"data": ...}`. Errors use `{"error": {"code": "...", "message": "..."}}`.

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/health` | Service and database health | Public |
| `GET` | `/api/games?date=YYYY-MM-DD` | Games for a specific JST date | Public |
| `GET` | `/api/games?month=YYYY-MM&team=ID` | Monthly or team schedule | Public |
| `GET` | `/api/games/{gamePk}` | Game details, linescore, decisions, box score, and analysis | User |
| `GET` | `/api/games/{gamePk}/status` | Lightweight game-status refresh | User |
| `POST` | `/api/games/{gamePk}/analyses` | Generate or retrieve game analysis | User |
| `GET` | `/api/standings` | Standings for all six divisions | Public |
| `GET` | `/api/teams` | All 30 MLB teams | Public |
| `GET` | `/api/teams/{mlbTeamId}` | Team details and schedule context | User |
| `GET` | `/api/teams/{mlbTeamId}/schedule` | Weekly or monthly team schedule | User |
| `GET` | `/api/teams/{mlbTeamId}/roster` | Team roster | Public |
| `GET` | `/api/players/{mlbPlayerId}?lang=zh\|ja` | Player statistics, recent appearances, and cached analysis | User |
| `POST` | `/api/players/{mlbPlayerId}/analyses` | Generate or retrieve player analysis | User |
| `GET/POST` | `/api/auth/*` | Registration, login, logout, session, and Google OIDC | Mixed |
| `POST` | `/api/calendar/authorization` | Start Google Calendar authorization | User |
| `POST` | `/api/calendar/events` | Add a game to Google Calendar | User |
| `POST` | `/api/sync/games` | Manually trigger a current-game refresh | User |

## Run Locally with Docker

### Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose

### Start the application

```bash
git clone https://github.com/sibozhang/web-services-dev-kcgi.git
cd web-services-dev-kcgi/assignment/final-project
cp .env.example .env
```

Set at least `SECRET_KEY` and `JWT_SECRET_KEY` to secure random values in `.env`, then run:

```bash
docker compose up --build
```

Open:

- Client: `https://localhost:2027`
- API: `https://localhost:2028/api`
- Health check: `https://localhost:2028/api/health`

The local containers share an automatically generated self-signed development certificate. Your browser may show a certificate warning the first time you open either localhost URL. Production TLS is terminated by Azure App Service.

Database migrations run automatically after PostgreSQL becomes ready. To run them manually:

```bash
docker compose exec api flask --app wsgi:app db upgrade
```

Stop the application while preserving the database volume:

```bash
docker compose down
```

## Initialize MLB Data

Run a complete initial synchronization:

```bash
docker compose exec api flask --app wsgi:app sync-all --season 2026
```

Individual synchronization commands are also available:

```bash
docker compose exec api flask --app wsgi:app sync-teams
docker compose exec api flask --app wsgi:app sync-schedule --start 2026-03-25 --end 2026-09-27
docker compose exec api flask --app wsgi:app sync-standings --season 2026
docker compose exec api flask --app wsgi:app sync-rosters --season 2026
docker compose exec api flask --app wsgi:app sync-team-stats --season 2026
docker compose exec api flask --app wsgi:app sync-player-stats --season 2026
docker compose exec api flask --app wsgi:app sync-current-games --lookback-days 1
```

The production container scripts are:

```text
/app/scripts/bootstrap_sync.sh
/app/scripts/sync_worker.sh
```

The API container owns database migrations. Synchronization sidecars set `SKIP_DB_MIGRATIONS=1` to avoid concurrent migration attempts.

## Configuration

Copy `.env.example` to `.env` for local development. Do not commit real credentials.

### Core settings

| Variable | Purpose |
|---|---|
| `FLASK_ENV` | Runtime environment |
| `SECRET_KEY` | Flask session signing key |
| `JWT_SECRET_KEY` | JWT signing key; use at least 32 random bytes |
| `DATABASE_URL` | PostgreSQL connection URL using the psycopg driver |
| `MLB_SEASON` | Default season displayed by the application |
| `APP_TIMEZONE` | Application timezone; defaults to `Asia/Tokyo` |
| `CLIENT_URL` | Public client origin |
| `CORS_ORIGINS` | Comma-separated client origins allowed to call the API |
| `API_BASE_URL` | Public API origin injected into the client |
| `TLS_MODE` | `direct` locally or `proxy` behind Azure TLS termination |

### Authentication and Google services

| Variable | Purpose |
|---|---|
| `JWT_COOKIE_SAMESITE` | Use `None` for cross-origin secure cookies |
| `SESSION_COOKIE_SAMESITE` | Use `None` for cross-origin OAuth sessions |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_LOGIN_REDIRECT_URI` | Google OIDC callback URL |
| `GOOGLE_CALENDAR_REDIRECT_URI` | Google Calendar OAuth callback URL |
| `TOKEN_ENCRYPTION_KEY` | Fernet key used to encrypt stored Calendar tokens |
| `BASE_URL` | Public API origin used to construct server URLs |

Generate a Fernet key after installing the project dependencies:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For the live deployment, the authorized Google redirect URIs use the API host:

```text
https://kcgi-mlb-dugout-api-ddgdhjcpcah0augw.japaneast-01.azurewebsites.net/api/auth/google/callback
https://kcgi-mlb-dugout-api-ddgdhjcpcah0augw.japaneast-01.azurewebsites.net/api/calendar/callback
```

The authorized JavaScript origin is:

```text
https://kcgi-mlb-dugout-client-b3bgaqagafardzcu.japaneast-01.azurewebsites.net
```

Google sign-in requests only identity scopes. Calendar access is requested separately when an authenticated user explicitly connects Google Calendar.

### Gemini

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini API key |
| `GEMINI_MODEL` | Configurable Gemini model name |

Gemini receives only structured data prepared by the server. Analyses are generated on demand for scheduled games, live games, completed games, and player performance. Results are cached by a SHA-256 hash of the source data and language, so Chinese and Japanese outputs remain independent. If Gemini is unavailable, the MLB data pages continue to work and the client displays a retryable message.

## Testing

The automated test suite uses local fixtures and does not call MLB, Google, or Gemini by default.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
```

The suite covers status normalization, UTC/JST boundaries, inning conversion, MLB retry behavior, idempotent synchronization, standings parsing, REST serialization, authentication, JWT cookies, CSRF protection, client/server boundaries, OAuth state validation, Calendar deduplication, AI caching, graceful external-service failures, and container automation contracts.

Optional external-service smoke tests are available for local development:

```bash
python scripts/smoke_external_services.py
python scripts/smoke_external_services.py --google
python scripts/smoke_external_services.py --gemini
```

The Gemini smoke test sends a real API request and may consume quota.

## Project Structure

```text
final-project/
├── app/
│   ├── blueprints/api/       # REST routes and serializers
│   ├── commands/             # Flask synchronization commands
│   ├── models/               # SQLAlchemy domain models
│   └── services/             # MLB, AI, authentication, and Calendar services
├── client/                   # Independent HTML/CSS/JavaScript client
├── migrations/               # Alembic database migrations
├── scripts/                  # Bootstrap, worker, exploration, and smoke-test tools
├── tests/                    # Unit, integration, and fixture-based tests
├── docker-compose.yml        # Local client/API/PostgreSQL environment
├── Dockerfile                # API production image
├── AZURE_DEPLOYMENT.md       # Azure container deployment guide
└── wsgi.py                   # API application entry point
```

## Time and Data Rules

- Datetimes are stored as timezone-aware UTC values and displayed in JST.
- The home page defines “today” using the `Asia/Tokyo` calendar day before converting the query window to UTC.
- Pitching innings are stored using integer outs to avoid decimal-inning errors.
- External MLB identifiers are retained for stable synchronization and resource URLs.
- AI output is descriptive and based only on structured data already available to the server.

## Limitations and Future Work

- Historical player-season browsing and name-based player search
- Head-to-head records against every opponent
- League-relative percentiles and advanced visualizations
- A dedicated play-by-play timeline for live games
- Full Statcast pitch-level data, including velocity, spin, and movement

## Deployment

The production environment uses separate Azure App Service applications for the client and API, with PostgreSQL and synchronization workers running as API-side container components. See [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md) for the complete deployment procedure and required settings.

## Data Attribution

MLB data is obtained from the public MLB Stats API. This is an educational project and is not affiliated with or endorsed by Major League Baseball.
