# Sayem Md Sajjudul Islam: my tasks

**Role:** Docker engineer  ·  **Student ID:** 2401249  ·  **Branch:** `feature/docker-satellite-common`  ·  **Files in my package:** 31

Source: `1-Planning/Staffing-Plan/TerraRisk_RACI.xlsx` (the same data as the RTM and CODEOWNERS). *R* = I do it and push it, *A* = I sign it off, *C* = I must be asked, *I* = I am told.

## 1. RACI rows where I am responsible (R)

| ID | Deliverable | Where |
|---|---|---|
| D-01 | System architecture: document and presentation | 3-Design/Architecture/, 4-Implementation/ARCHITECTURE.md |
| D-06 | Docker and infrastructure design: 11 containers, networks, health | 3-Design/Docker-Design/ |
| I-16 | Satellite service: Earth Engine features, pictures, cache | 4-Implementation/services/satellite/ |
| I-17 | Common library tr_common: client, circuit breaker, registry, token | 4-Implementation/services/common/ |
| I-18 | Docker: Dockerfiles, docker-compose, ignore files, secrets folder | 4-Implementation/ (root) |
| I-19 | Developer scripts: run all services, end-to-end check | 4-Implementation/scripts/ |
| T-01 | Service tests (65 tests): each member tests their own service | 4-Implementation/services/tests/ |
| T-03 | End-to-end check over real HTTP (scripts/e2e_check.py) | 4-Implementation/scripts/ |
| T-04 | Test evidence kept up to date in the RTM | 2-Analysis/Requirements/ |
| O-03 | Push your own part to GitHub (branch, pull request, fix review comments) | the whole repository |

I am accountable (A) for 0 row(s).

## 2. RACI rows where I must be consulted (C): 22

- **P-02** Feasibility Analysis: technical, operational, economic
- **P-03** Staffing Plan: roster, roles, RACI matrix
- **P-04** Project Standards: Git workflow, branches, commits, reviews, coding rules
- **P-05** Risk Assessment: risk register and mitigations
- **P-06** GitHub repository: folder structure, READMEs, protection, CODEOWNERS
- **A-01** Requirements and use cases (63 requirements, 10 use cases)
- **A-02** Requirements Traceability Matrix (RTM)
- **A-03** Data and model analysis: datasets, cross-validation, limits
- **D-02** Integration design: website gateway, orchestration, API contracts, data
- **D-04** Subscription and billing design (Design B, ledger, idempotency)
- **D-05** AI and model design: flood, landslide, persona views, advisory, chatbot
- **D-07** Deployment design and runbook: server, HTTPS, environment, CI/CD
- **I-01** Django project: settings, URLs, gateway to the services, views
- **I-03** Analysis orchestrator service
- **I-04** Geocode service: place search, reverse, IP lookup, cache
- **I-09** Billing service: accounts, credits, ledger, purchases, plans
- **I-11** Report service: PDF certificate
- **I-13** ML pipeline: datasets, training scripts, model files
- **I-21** Environment settings and secret handling (.env.example)
- **I-22** Reverse proxy: nginx configuration (container and host)
- **O-01** CI/CD pipeline: tests on every pull request, deploy from main
- **O-02** Live server: host, domain, HTTPS, environment, releases and rollback

I am only informed (I) on 13 rows (P-01, D-03, I-02, I-05, I-06, I-07, I-08, I-10, I-12, I-14, I-15, I-20, T-02).

## 3. Requirements I answer for (R): 16

| ID | Requirement | Status |
|---|---|---|
| FR-04 | Satellite features and pictures | Implemented |
| ARC-06 | Same code, two transports | Implemented |
| NFR-03 | Bounded latency | Implemented |
| NFR-04 | Retry once and circuit breaker | Implemented |
| NFR-05 | Service-to-service authentication | Implemented |
| NFR-09 | Observability | Implemented |
| NFR-12 | Independent scaling | Implemented |
| NFR-13 | Consistent, safe error handling | Implemented |
| NFR-14 | Portability across run modes | Implemented |
| NFR-17 | Asynchronous jobs for slow work | Planned |
| OPS-01 | Container deployment (11 containers) | Implemented |
| OPS-04 | Run everything without Docker | Implemented |
| OPS-05 | One-command end-to-end check | Implemented |
| DOC-01 | Architecture document | Implemented |
| DOC-03 | Architecture presentation | Implemented |
| DOC-05 | Honest-limits statement | Implemented |

## 4. Requirements where I am consulted (C): 22

FR-07, ARC-01, ARC-02, ARC-03, ARC-05, ML-01, ML-02, NFR-01, NFR-10, NFR-11, NFR-18, NFR-19, NFR-20, OPS-02, OPS-03, OPS-06, OPS-07, DOC-02, DOC-04, DOC-06, DOC-07, DOC-08

## 5. My files, by folder

| Folder | Files |
|---|---|
| 3-Design/Architecture | 2 |
| 3-Design/Docker-Design | 1 |
| 4-Implementation | 5 |
| 4-Implementation/scripts | 2 |
| 4-Implementation/secrets | 1 |
| 4-Implementation/services | 1 |
| 4-Implementation/services/common | 7 |
| 4-Implementation/services/satellite | 8 |
| 4-Implementation/services/tests | 4 |

The full list with sizes and hashes is in `MANIFEST.csv`.

## 6. Defects and gaps that I own (RTM sheet *Defects & Gaps*)

| ID | Title | Severity | Status |
|---|---|---|---|
| DEF-01 | End-to-end script reuses a fixed billing key | Low | Open |
| GAP-01 | web and proxy containers have no health check or log rotation | Low | Open |
| GAP-03 | Container images never built | High | Open |

## 7. After my pull request is open

1. Open items you own: DEF-01 (the end-to-end script reuses the fixed key `k1`: use a key that is unique per run), GAP-01 (health checks and log rotation for web and proxy) and GAP-03 (the images were never built: run `docker compose up -d --build` on a machine with Docker and write the result in the RTM).
2. Your pull request is merged FIRST (it brings the shared library `tr_common` that the others' tests need). Abduraimboy reviews it; you review the Leader's pull request.
3. `test_satellite.py` runs on your own part; `test_common.py` checks all eight services at once, so it passes after the last merge. Pull the whole repository (`git pull origin main`) before building images: the Dockerfiles need every service.

## 8. Definition of done (Project Standards)

The code and its test are merged; the tests pass; the documents and the RTM are updated; the owner and the reviewer agree in the pull request; nothing secret is in the diff.
