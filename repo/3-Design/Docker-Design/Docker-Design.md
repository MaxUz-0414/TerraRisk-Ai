# Docker and Infrastructure Design

| | |
|---|---|
| **Owner** | Sayem Md Sajjudul Islam (Docker). Accountable: Abduraimboy Murodullaev. Consulted: Farhad (deployment), Ramuna (model files in the image) |
| **Version / date** | 1.0, 19 November 2026 |
| **Code** | `4-Implementation/docker-compose.yml`, `Dockerfile`, `services/Dockerfile`, `.dockerignore`, `nginx/`, `services/common/`, `services/satellite/`, `scripts/` |
| **RTM** | OPS-01, OPS-03 to OPS-05, ARC-06, NFR-03 to NFR-05, NFR-09, NFR-11 to NFR-14, FR-04 |

## 1. The 11 containers

| Container | Image / build | Networks | Volumes | Health check |
|---|---|---|---|---|
| `proxy` | `nginx:1.27-alpine` | edge | `nginx/default.conf`, static and media (read-only) | none yet (GAP-01) |
| `web` | `Dockerfile` (Django + gunicorn) | edge, backend | `static_data`, `media_data` | none yet (GAP-01) |
| `db` | `postgres:16-alpine` | backend | `pg_data` | yes |
| `analysis`, `risk`, `advisory`, `chatbot` | `services/Dockerfile` (`SERVICE=<name>`) | backend | none | yes |
| `satellite` | `services/Dockerfile` | backend | `satellite_cache`, `./secrets` (read-only, the Earth Engine key) | yes |
| `report` | `services/Dockerfile` | backend | none | yes |
| `billing` | `services/Dockerfile` | backend | `billing_data` | yes |
| `geocode` | `services/Dockerfile` | backend | `geocode_data` | yes |

Two networks: **edge** (proxy ↔ web) and **backend** (everything else, nothing published). **Only `proxy` publishes a port.**
All 11 containers use `restart: unless-stopped`. The eight services share one `x-service` block (restart policy, the backend
network, log rotation with `json-file`, 10 MB × 3 files); `web`, `db` and `proxy` have no log rotation yet (GAP-01).

## 2. Images

- **Website** (`Dockerfile`): `python:3.12-slim`, install `requirements.txt`, copy the project, run `migrate`, `collectstatic`, then gunicorn with `WEB_WORKERS` (default 2) × `WEB_THREADS` (default 4), timeout 200 s. The website waits for services during an analysis, so few workers with several threads.
- **Services** (`services/Dockerfile`, one recipe for all eight): build argument `SERVICE`; installs the shared library's and the service's own requirements; copies `services/common` and `services/<name>` only; runs as a non-root user (uid 10001); `/data` is the volume for the service's own files; a built-in `HEALTHCHECK` calls `/healthz`; gunicorn with **one worker and eight threads** on purpose (counters and caches live in memory, SQLite wants one writer: scale by running more containers). The chatbot trains its model while the image is built.
- `.dockerignore` keeps `.git`, `.github`, virtual environments, `.env`, databases, media and `secrets/*` out of the build context.

## 3. Start-up and trust

- `INTERNAL_TOKEN` is **required** (`${INTERNAL_TOKEN:?...}`): compose refuses to start without it. Every service checks `X-Service-Token` with a constant-time comparison and answers 401 without it (except `/healthz`).
- `web` waits (`depends_on`) for the services; `analysis` waits for satellite, risk, advisory, geocode; `report` waits for satellite.
- `proxy` passes the visitor's real IP (`X-Real-IP`, `CF-Connecting-IP`), keeps the original scheme behind a TLS-terminating proxy, gzips text, serves `/static/` with a 7-day expiry, allows 10 MB bodies and waits up to 210 s for slow analyses.

## 4. The shared library `tr_common` (`services/common/`)

Service factory (health, token check, JSON errors, request id, request counters), HTTP client (timeout per service, one retry on
GET, **circuit breaker: 5 failures in a row opens it for 15 s**), registry (the same call works in-process or over HTTP), config
helpers. Timeouts: analysis 170 s, satellite 130, report 120, advisory 30, chatbot 25, risk 15, geocode 10, billing 10.

## 5. Three ways to run the same code

| Mode | Command | For |
|---|---|---|
| in-process | `SERVICES_MODE=inprocess python manage.py runserver` (default) | laptops, unit tests |
| separate processes | `python scripts/run_services.py`, then `SERVICES_MODE=http python manage.py runserver` | seeing real HTTP behaviour without Docker |
| containers | `docker compose up -d --build` | production |

`python scripts/e2e_check.py` checks a running stack over real HTTP (22 checks run so far: 21 pass, 1 test-script defect, DEF-01).

## 6. Satellite service

One service for features **and** pictures: same Earth Engine session, credentials, cache and demo/live switch.
`POST /v1/features`, `GET /v1/layers`, `POST /v1/layers/<truecolor|ndvi|heat|water>`; picture cache is a volume that can be
deleted at any time. Demo mode (`USE_FAKE_DATA=True`) gives deterministic values and labelled illustrations.

## 7. Open items

- **Build the 11 images on a real Docker host** (GAP-03, risk R-01): the first `docker compose up -d --build` is the first real test of the container build.
- Add health checks to `web` and `proxy`, and log rotation to `web`, `db`, `proxy` (GAP-01).
- Fix the end-to-end script's fixed billing key (DEF-01): use `key = f"e2e-{user}"`.
- Scheduled backups of `pg_data` and `billing_data` (with Farhad, R-10).
