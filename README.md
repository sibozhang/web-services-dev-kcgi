# Web Services Development

Coursework, laboratory exercises, and the final project for the **Web Services Development** course at the Kyoto College of Graduate Studies for Informatics (KCGI), Spring 2026.

## Featured Project: MLB Dugout

The main project in this repository is **MLB Dugout**, a deployed full-stack web service for exploring Major League Baseball games, standings, teams, rosters, and player performance.

[**View the source code and full documentation →**](assignment/final-project/)

| Resource | Link |
|---|---|
| Live application | [Open MLB Dugout](https://kcgi-mlb-dugout-client-b3bgaqagafardzcu.japaneast-01.azurewebsites.net/) |
| REST API | [Open the API](https://kcgi-mlb-dugout-api-ddgdhjcpcah0augw.japaneast-01.azurewebsites.net/) |
| API health check | [View service status](https://kcgi-mlb-dugout-api-ddgdhjcpcah0augw.japaneast-01.azurewebsites.net/api/health) |

MLB Dugout uses a strictly separated Client/Server architecture:

- An independent HTML, CSS, and Vanilla JavaScript client
- A Flask REST API with credential-aware CORS
- PostgreSQL with SQLAlchemy and Alembic migrations
- Server-side synchronization with the MLB Stats API
- Email/password authentication and Google OpenID Connect
- Google Calendar integration
- On-demand Gemini analysis for games and players
- Docker-based local development and Azure App Service deployment

The interface supports Chinese and Japanese, displays schedules in Japan Standard Time, and provides live game information, box scores, division standings, team rosters, player statistics, and recent appearances.

## Repository Structure

```text
web-services-dev-kcgi/
├── assignment/
│   ├── assign01/           # Introductory Flask JSON API
│   ├── assign02/           # Client/server exercise with CORS
│   ├── assign03/           # Database, authentication, roles, and OAuth
│   └── final-project/      # MLB Dugout full-stack web service
├── lab/
│   ├── lab01_basic_service/ # Basic Flask routes and JSON requests
│   └── lab02_frontend/      # Introductory web client exercise
├── pyproject.toml           # Shared Python project metadata
└── uv.lock                  # Reproducible Python dependency lockfile
```

### [`assignment/`](assignment/)

Independent course assignments that build progressively from a small Flask API to database-backed services and authentication.

| Folder | Contents |
|---|---|
| [`assign01`](assignment/assign01/) | A basic Flask service with JSON-file persistence, structured responses, and common HTTP status handling. |
| [`assign02`](assignment/assign02/) | A separated browser client and Flask API demonstrating cross-origin requests with CORS. |
| [`assign03`](assignment/assign03/) | A PostgreSQL-backed service covering SQLAlchemy models, JWT authentication, role-based access, and OAuth integrations. |
| [`final-project`](assignment/final-project/) | The complete MLB Dugout application, including the client, REST API, migrations, synchronization workers, tests, Docker configuration, and Azure deployment guide. |

### [`lab/`](lab/)

Small in-class exercises used to practice individual web-service concepts before applying them in the assignments.

| Folder | Contents |
|---|---|
| [`lab01_basic_service`](lab/lab01_basic_service/) | Basic Flask endpoints, route parameters, query parameters, and JSON request handling. |
| [`lab02_frontend`](lab/lab02_frontend/) | A simple HTML/CSS frontend exercise that introduces the client side of a web service. |

## Running the Final Project

The recommended entry point is the dedicated [MLB Dugout README](assignment/final-project/README.md), which includes:

- Architecture and feature documentation
- REST API resources
- Docker Compose setup
- Environment-variable reference
- MLB data initialization and synchronization
- Google OAuth, Google Calendar, and Gemini configuration
- Automated testing instructions
- Azure deployment guidance

For a quick local start:

```bash
cd assignment/final-project
cp .env.example .env
# Set secure local values in .env before starting the services.
docker compose up --build
```

Then open `https://localhost:2027` in a browser. The local development environment uses a self-signed HTTPS certificate.

## Notes

- Each assignment is preserved as a record of the concepts covered at that stage of the course.
- The final project has its own dependencies, Docker configuration, tests, and detailed documentation.
- Real credentials and local environment files are intentionally excluded from version control.
- MLB data is obtained from the public MLB Stats API. MLB Dugout is an educational project and is not affiliated with or endorsed by Major League Baseball.
