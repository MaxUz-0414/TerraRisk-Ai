# Staffing Plan: TerraRisk AI

| | |
|---|---|
| **Owner** | Abduraimboy Murodullaev (Leader) |
| **Version / date** | 1.0, 19 November 2026 |
| **Companion file** | [`TerraRisk_RACI.xlsx`](TerraRisk_RACI.xlsx): the RACI matrix, the requirement owners and a map of every file to its owner |

## 1. Team and roles

| # | Member | Student ID | Role | Branch |
|---|---|---|---|---|
| 1 | **Abduraimboy Murodullaev** (Leader) | 2401248 | Project Leader and web integration | `feature/leader-integration-planning` |
| 2 | **Anvarjon Gulomov** | 2401067 | Frontend developer | `feature/frontend-ui` |
| 3 | **Barsha Ghimire** | 2400881 | Subscription, billing and accounts developer | `feature/subscription-billing` |
| 4 | **Ramuna Sunwar** | 2400991 | AI / machine-learning engineer | `feature/ai-models` |
| 5 | **Sayem Md Sajjudul Islam** | 2401249 | Docker engineer | `feature/docker-satellite-common` |
| 6 | **Md Farhad Hossain** | 2401252 | Deployment (DevOps) engineer | `feature/deployment-cicd` |


## 2. What each member owns

| Member | Owns (folders and files) | Code files | Lines of code |
|---|---|---|---|
| **Abduraimboy Murodullaev** | `analysis/` app, `config/`, `core/` (services gateway, views, URLs, tests), `services/analysis/`, `services/geocode/`, `manage.py`, requirements, `4-Implementation/README.md`; the repository set-up (folders, ignore files, CODEOWNERS, pull-request template), Project Standards, planning and analysis documents, the RTM and the RACI | 45 | 3,070 |
| **Anvarjon Gulomov** | `templates/` (except pricing, checkout, profile, registration), `static/` (CSS, JS, images), Tailwind setup, `core/team.py`, context processors and template tags | 41 | 2,691 |
| **Barsha Ghimire** | `accounts/`, `services/billing/`, `services/report/`, the pricing, checkout, profile and registration templates | 34 | 1,801 |
| **Ramuna Sunwar** | `services/risk/` (with the model files), `services/advisory/`, `services/chatbot/`, `ml/`, `data/`, `check_gemini.py` | 34 | 2,092 |
| **Sayem Md Sajjudul Islam** | `docker-compose.yml`, both Dockerfiles, `.dockerignore`, `.gitignore` and `secrets/` of `4-Implementation/`, `services/common/`, `services/satellite/`, `scripts/`, service tests base, `ARCHITECTURE.md`, the architecture documents and deck, the Docker design | 28 | 2,427 |
| **Md Farhad Hossain** | `.github/workflows/`, `.env.example`, `nginx/`, `core/dashboard.py`, `core/admin_site.py`, `core/admin_apps.py`, `core/netutil.py`; deployment design and runbook | 7 | 397 |


Files that several members' features meet in (`core/views.py`, `core/urls.py`, `core/tests.py`, `analysis/tests.py`) are
pushed by the Leader; the other owners are co-owners in `.github/CODEOWNERS` and review changes to their own part.

## 3. RACI summary

*R = responsible (does the work and pushes it), A = accountable (signs off; exactly one per row), C = consulted
before the work is final, I = informed.* The Leader is accountable for every deliverable (reviews and merges the pull
request) and also administers the repository itself (folders, protection, CODEOWNERS). The full matrix with all 45 rows is in the workbook; this
table counts the roles.

| Member | R | A | C | I | Rows where the member is responsible |
|---|---|---|---|---|---|
| Abduraimboy Murodullaev | 17 | 45 | 0 | 0 | P-01, P-02, P-03, P-04, P-05, P-06, A-01, A-02, D-02, I-01, I-02, I-03, I-04, T-01, T-02, T-04, O-03 |
| Anvarjon Gulomov | 6 | 0 | 18 | 21 | D-03, I-05, I-06, I-07, T-04, O-03 |
| Barsha Ghimire | 8 | 0 | 17 | 20 | D-04, I-08, I-09, I-10, I-11, T-01, T-04, O-03 |
| Ramuna Sunwar | 9 | 0 | 20 | 16 | A-03, D-05, I-12, I-13, I-14, I-15, T-01, T-04, O-03 |
| Sayem Md Sajjudul Islam | 10 | 0 | 22 | 13 | D-01, D-06, I-16, I-17, I-18, I-19, T-01, T-03, T-04, O-03 |
| Md Farhad Hossain | 8 | 0 | 16 | 21 | D-07, I-20, I-21, I-22, T-04, O-01, O-02, O-03 |


## 4. How the work reaches GitHub

Each member receives a package (a zip with their files already in the right folders) and pushes it on their own branch.
Merge order (the order keeps `main` consistent; nothing breaks if it is changed, but CI is only meaningful at the end):

1. **Sayem**: `feature/docker-satellite-common` (shared library, Docker files, satellite service, scripts, architecture); it is merged first because it brings the shared library the others' tests need
2. **Abduraimboy**: `feature/leader-integration-planning` (Django project, analysis app, analysis and geocode services, planning and analysis documents); the repository skeleton (step 1) was pushed straight to `main` before anybody else pushed
3. **Barsha**: `feature/subscription-billing` (accounts, billing and report services, pricing and checkout pages)
4. **Ramuna**: `feature/ai-models` (risk, advisory and chatbot services, `ml/`, `data/`)
5. **Anvarjon**: `feature/frontend-ui` (templates, static files, team section)
6. **Farhad**: `feature/deployment-cicd` **last**: it brings the CI workflow, which then runs for the first time on a complete repository

## 5. Communication and decisions

- All code and document changes happen in pull requests; the discussion stays in the pull request.
- The Leader decides disputes about scope, repository structure and tooling.
- A member who is blocked tells the Leader the same day; a member who will miss a deadline tells the Leader before it.
- Weekly check: the RTM *Dashboard* sheet (every number is a formula) and the open items in the Risk Assessment.

## 6. Changing this plan

Edit `TerraRisk_RACI.xlsx` (change a letter; the checks on the *RACI* sheet must stay "OK"), update the owner of the affected
files in `.github/CODEOWNERS`, and open a pull request.
