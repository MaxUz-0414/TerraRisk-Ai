# Risk Assessment: TerraRisk AI

| | |
|---|---|
| **Owner** | Abduraimboy Murodullaev (Leader). Consulted: every member for the risks in their area |
| **Version / date** | 1.0, 19 November 2026 |
| **Method** | Likelihood (1 low, 2 medium, 3 high) × impact (1 low, 2 medium, 3 high) = score. Score 6 or more: act now; 3 to 4: plan; 1 to 2: watch. |
| **Status of the ratings** | First assessment by the Leader from the evidence in the RTM; to be reviewed with the team and changed where members disagree. |

Items that come from the RTM (sheet *Defects & Gaps*) carry the same id there.

## Risk register

| ID | Risk | L | I | Score | Mitigation | Owner | Source |
|---|---|---|---|---|---|---|---|
| R-01 | The 11-container image build has never run on a real Docker host; a build error would block deployment | 2 | 3 | **6** | Run `docker compose up -d --build` on a clean machine, fix, record it in the RTM | Sayem | GAP-03 |
| R-02 | Earth Engine and the live map imagery were never called for real; live mode could fail or be slow (10 to 60 s per query) | 2 | 3 | **6** | One real run with a service account; the services already fail safe (clear message, no credit used) | Sayem, Ramuna | GAP-02 |
| R-03 | The first pull requests may touch files that several people edit (`core/views.py`) and cause merge conflicts | 2 | 2 | 4 | Those files are pushed once, by the Leader; co-owners review; later changes go through small pull requests | Leader | Staffing Plan |
| R-04 | A secret (key, `.env`, database) is committed by mistake | 1 | 3 | 3 | `.gitignore`/`.dockerignore`, the rule "rotate first" in the Standards, a check of `git status` before every push | All | Project Standards |
| R-05 | The CI step `docker compose config` failed whenever `.env` was missing | 3 | 2 | **6** | Fixed in the repository workflow: `cp .env.example .env` before the step (tested: exit 1 without, exit 0 with) | Farhad | DEF-03 |
| R-06 | The CI deploy job still targets the *AZURE_VM_** secrets while the live server is a different cloud server, and the server folder is not a git clone yet | 3 | 2 | **6** | Decide one target; create a git clone on the server; set the three secrets; see the Deployment Design | Farhad | GAP-09 |
| R-07 | The live server is small (1 GB RAM, shared with other sites); eleven containers may run out of memory | 2 | 3 | **6** | Fewer gunicorn workers (already reduced on the server), monitor memory on the admin dashboard, upgrade the server if needed | Farhad | live deployment notes |
| R-08 | Billing uses one SQLite file: a second billing replica would corrupt the idea of "one writer" | 1 | 3 | 3 | Keep one billing container; plan the move to PostgreSQL (NFR-20) | Barsha | GAP-10, NFR-20 |
| R-09 | The idempotency key is unique across all users, so a client that reuses a key for another user is silently ignored | 1 | 2 | 2 | Scope the key to (user, key) in `store.py`; the web app already builds unique keys | Barsha | DEF-02 |
| R-10 | No scheduled backup of PostgreSQL and the `billing_data` volume | 2 | 3 | **6** | Add a nightly dump and volume copy; test a restore once | Farhad, Sayem | README, GAP-10 |
| R-11 | The flood model is trained on formula-made labels, so a user could read the score as a validated forecast | 2 | 3 | **6** | The pages and PDF already say "screening index"; replace the labels with real flood records when available | Ramuna | GAP-08 |
| R-12 | The landslide model is modest (AUC about 0.70) and trained on 600 rows | 2 | 2 | 4 | Keep wording "relative index"; add events and features; publish the metric (NFR-16) | Ramuna | ML-02 |
| R-13 | The Gemini model name in the default settings may be retired by Google (it happened once) | 2 | 2 | 4 | Templates take over automatically; keep `GEMINI_MODEL` in `.env`, check `check_gemini.py` before demos | Ramuna | AI notes |
| R-14 | Maps were never drawn by real Leaflet in a browser in the build environment; layout or script errors could appear | 2 | 2 | 4 | Open every page in Chrome and Safari once; fix; record in the RTM | Anvarjon | GAP-04 |
| R-15 | The web test suite (105 tests) was not re-run for the matrix because Django could not be installed in the build environment | 2 | 2 | 4 | Run `python manage.py test` on a team laptop and update the RTM evidence | Leader | GAP-05 |
| R-16 | No load or performance numbers; the server may be slow when several users analyse at once | 2 | 2 | 4 | A small load test with the end-to-end script; record in the RTM | Farhad | GAP-07 |
| R-17 | Third-party policies (Nominatim 1 req/s, Esri and Google imagery terms, Earth Engine non-commercial) are broken by growth | 1 | 3 | 3 | Geocode service enforces the rate and caches; check the terms before any commercial use | Leader | System Request |
| R-18 | IP-based sign-in locations are stored (city level); privacy expectations differ by country | 1 | 2 | 2 | Private addresses are never looked up; state it in the privacy page; delete old events on request | Barsha | NFR-07 |
| R-19 | A team member is unavailable near the deadline | 2 | 2 | 4 | Each area has a consulted member (RACI); the backup package contains every file so anyone can push another member's part | Leader | Staffing Plan |
| R-20 | The end-to-end check script fails on a second run (it reuses a fixed billing key) and hides a real regression | 3 | 1 | 3 | Use a fresh key per run: `key = f"e2e-{user}"` | Sayem | DEF-01 |
| R-21 | When the code moves into `4-Implementation/`, Docker Compose names the project `4-implementation`; on the live server the existing volumes (`terrarisk_*`) would not be found and the site would start with an empty database | 3 | 3 | **9** | Add `COMPOSE_PROJECT_NAME=terrarisk` to the server `.env` before the first deploy from the repository; rehearse on a spare machine; back up first (Deployment Design, section 5) | Farhad | GAP-12 |

## Top risks to close first (score 6)

R-21 (score 9: before the live server is moved to the repository), then R-01, R-02, R-05 (already fixed in the repository workflow), R-06, R-07, R-10, R-11.

## Review

Re-score every risk in the weekly meeting. When a mitigation is done, change its row to "closed", note the date and the
evidence (test, run, link), and update the matching row in the RTM.
