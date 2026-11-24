# Deployment Design and Runbook

| | |
|---|---|
| **Owner** | Md Farhad Hossain (Deployment). Accountable: Abduraimboy Murodullaev. Consulted: Sayem (containers) |
| **Version / date** | 1.0, 19 November 2026 |
| **Code** | `.github/workflows/deploy.yml`, `4-Implementation/.env.example`, `core/dashboard.py`, `core/admin_site.py`, `core/admin_apps.py`, `core/netutil.py`, `nginx/default.conf` |
| **RTM** | OPS-02, OPS-03, OPS-06, FR-10, NFR-18, NFR-19 |

> **Keep this file free of secrets.** Server addresses, e-mail addresses, passwords and keys are **not** written in the
> repository. Use the placeholders below and keep the real values in the team's private notes or in GitHub secrets.

## 1. Environments

| Environment | How it runs | Used for |
|---|---|---|
| Laptop, in-process | `python manage.py runserver` (`SERVICES_MODE=inprocess`) | development, tests |
| Laptop, containers | `docker compose up -d --build` from `4-Implementation/` | trying the real stack |
| Live server | Docker Compose on a small cloud VM behind a host-level nginx with HTTPS | the public site |

## 2. The live system (as of the 7 Nov 2026 deployment notes)

- A small cloud server (Ubuntu 24.04, 1 GB RAM plus 2 GB swap) that **also hosts other sites**, so TerraRisk must not take ports 80 or 443.
- **Host nginx** (shared) has one site file for TerraRisk that forwards to `127.0.0.1:8081`, which is TerraRisk's own `proxy` container; that talks to `web` (gunicorn), which talks to `db` (its own PostgreSQL 16).
- **HTTPS**: a Let's Encrypt certificate from `certbot --nginx` with an http to https redirect; certbot's timer renews it.
- **DNS**: managed at the domain registrar (`<your-domain>` points to the server).
- **Code**: uploaded from a zip of the earlier merged version; there is **no git repository on the server yet**, so the GitHub Actions deploy is not active (GAP-09).
- **`.env` on the server**: `DJANGO_DEBUG=False`, a random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS=https://<your-domain>`, `USE_HTTPS=True`, `USE_FAKE_DATA=True` (no Earth Engine key yet), payments in demo mode.

## 3. Environment variables (names only; values live in `.env`, never in Git)

| Variable | Purpose | Needed |
|---|---|---|
| `INTERNAL_TOKEN` | shared secret between website and services; compose refuses to start without it | **yes** |
| `DJANGO_SECRET_KEY` | Django signing key (long random text) | **yes in production** |
| `POSTGRES_PASSWORD` (`POSTGRES_USER`, `POSTGRES_DB`...) | database login | **yes in production** |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `USE_HTTPS` | production web settings | yes |
| `USE_FAKE_DATA` | `True` demo data, `False` real Earth Engine data | yes |
| `GEE_PROJECT`, `GEE_SERVICE_ACCOUNT`, `GEE_KEY_FILE` | Earth Engine (key file goes in `./secrets/`, read by the satellite service) | for live data |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | written advice and chatbot fallback | optional |
| `GOOGLE_MAPS_API_KEY` | Google tiles instead of Esri labels | optional |
| `PAYMENTS_DEMO` | `True` = checkout records a purchase and charges nobody | yes |
| `CLIENT_IP_HEADERS` | where the visitor's real IP is read from | optional |
| `AZURE_ACCOUNT_NAME`, `AZURE_ACCOUNT_KEY`, `AZURE_CONTAINER` | PDF storage in Azure Blob | optional |
| `SUPPORT_EMAIL`, `INSTAGRAM_URL`, `TWITTER_URL`, `GITHUB_URL` | footer and support page | optional |
| `WEB_WORKERS`, `WEB_THREADS` | gunicorn workers and threads of the website (defaults 2 and 4) | small servers: 1 and 4 |
| `COMPOSE_PROJECT_NAME` | see section 5 (important on the live server) | live server |

## 4. CI/CD (`.github/workflows/deploy.yml`)

```
pull request or push to main
 â””â”€ test job (working directory 4-Implementation/)
      1  python -m unittest discover -s services/tests -t services -v      65 service tests
      2  python manage.py test                                              105 website tests
      3  python manage.py makemigrations --check --dry-run                  migrations up to date
      4  cp .env.example .env  +  INTERNAL_TOKEN=ci docker compose config -q   compose file valid
push to main only, after the test job
 â””â”€ deploy job: SSH to the server, cd ~/terrarisk, git pull origin main, cd 4-Implementation,
                docker compose up -d --build, docker compose ps, curl --fail http://127.0.0.1:8081/healthz/
```

- **Fix made for the new repository layout:** step 4 now copies `.env.example` to `.env` first. Tested: without a `.env`, `docker compose config` exits 1 (it cannot read `env_file: .env`); with it, exit 0 (DEF-03).
- The repository secrets are named `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY` (historical names: they may point to any server). Set them under *Settings, Secrets and variables, Actions*.
- The deploy job runs only on a push to `main` that follows a green test job.

## 5. Moving the live server to the Git repository (one time)

The server folder is not a Git clone, and the code now lives in `4-Implementation/`. **Docker Compose names the project after the
folder that holds `docker-compose.yml`; from `4-Implementation/` that would be `4-implementation`, and the existing volumes
(`terrarisk_pg_data`, `terrarisk_billing_data`...) would no longer be found, so the site would start with an empty database.**
The fix is one line in the server's `.env`:

```
COMPOSE_PROJECT_NAME=terrarisk
```

(tested with `docker compose config`: the volumes keep the names `terrarisk_*`). Steps, to be rehearsed on a spare machine first:

1. **Back up** (section 7): PostgreSQL dump and the billing volume.
2. Keep a copy of the current folder: `mv ~/terrarisk ~/terrarisk-zip-backup`.
3. `git clone <repository-url> ~/terrarisk` (use a deploy key or a token; never put it in the repository).
4. Copy `.env` and the `secrets/` files from the backup folder into `~/terrarisk/4-Implementation/`, and add `COMPOSE_PROJECT_NAME=terrarisk` to that `.env`.
5. Two server-only changes used to be edited into tracked files. Keep them **out of Git** instead:
   - port: create `4-Implementation/docker-compose.override.yml` (it is ignored by `.gitignore`):
     ```yaml
     services:
       proxy:
         ports: !override
           - "127.0.0.1:8081:80"
     ```
     (tested with `docker compose config`: the port 80 mapping is replaced, not added to);
   - memory: add `WEB_WORKERS=1` and `WEB_THREADS=4` to the server's `.env` instead of editing the `Dockerfile`.
6. `cd ~/terrarisk/4-Implementation && docker compose up -d --build`, then `docker compose ps` (all `healthy`) and `curl -s http://127.0.0.1:8081/healthz/`.
7. Check a sign-in with an existing account, then add the three Actions secrets so that pushes to `main` deploy.

## 6. Everyday commands (in `~/terrarisk/4-Implementation`)

| Task | Command |
|---|---|
| status | `docker compose ps` |
| logs of one service | `docker compose logs -f web` (replace `web`) |
| follow one user action through all services | `docker compose logs \| grep <request-id>` |
| health | `curl -s http://127.0.0.1:8081/healthz/` |
| apply a changed `.env` | `docker compose up -d` |
| apply new code by hand | `git pull origin main && docker compose up -d --build` |
| create an administrator | `docker compose exec web python manage.py createsuperuser` |
| roll back | `git checkout <previous-commit>` then `docker compose up -d --build` |

## 7. Backups (to be set up and tested: risk R-10)

What must be saved together: PostgreSQL (`pg_data`) and the billing database (`billing_data`). Geocode and satellite caches can be deleted at any time.

```
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > terrarisk-$(date +%F).sql
docker volume ls | grep billing_data        # exact name, e.g. terrarisk_billing_data
docker run --rm -v <that-volume>:/data -v "$PWD":/backup alpine tar czf /backup/billing-$(date +%F).tgz -C /data .
```

These commands have not been run on the server yet. Test a **restore** on a spare machine before relying on them.

## 8. Admin dashboard back end (`core/dashboard.py`)

`kpis()`, `growth()`, `analyses_by_day()`, `logins_by_day()`, `activity_heatmap()`, `risk_mix()`, `persona_mix()`,
`login_geo()`, `places()`, `revenue()`, `storage()`, `events()`, `system_metrics()` (server CPU and memory) and `live()`
(health of the eight services, polled by the page at `/admin/dashboard/live/`). The page is `templates/admin/terra_index.html`
(Anvarjon). `admin_site.py` makes the dashboard the home page of the real Django admin; only staff users can open it.
The visitor's IP for the sign-in map comes from `CF-Connecting-IP` or `X-Real-IP` (`netutil.py`); without Cloudflare in front,
a visitor can forge `CF-Connecting-IP`, so treat that chart as informational, never as security.

## 9. Cloudflare option for HTTPS

Put the domain on Cloudflare, A record to the server, SSL/TLS mode **Full**, `USE_HTTPS=True` in `.env`. Cloudflare serves
HTTPS and nginx can stay on port 80. (The live site currently uses Let's Encrypt on the host nginx instead.)

## 10. Open items

- CI/CD workflow updated (`SERVER_*` secrets and `/healthz/` check added for GAP-09); live server migration pending section 5.
- Health checks for `web` and `proxy` (with Sayem, GAP-01); metrics beyond the dashboard (NFR-18, planned); service-to-service TLS (NFR-19, planned).
- A load test (GAP-07) and a restore test (R-10).
