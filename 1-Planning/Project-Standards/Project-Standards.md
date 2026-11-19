# Project Standards: TerraRisk AI

| | |
|---|---|
| **Owner** | Abduraimboy Murodullaev (Leader and repository administrator). Consulted: every member |
| **Version / date** | 1.0, 19 November 2026 |
| **Applies to** | every member, every change, every folder |

## 1. Repository layout

```
1-Planning/        documents of the planning phase (System Request, Feasibility, Staffing Plan, Standards, Risks)
2-Analysis/        requirements, use cases, RTM, data and model analysis
3-Design/          architecture and the design document of each area
4-Implementation/  ALL source code and the files that build and run it (Docker, tests, scripts, data)
.github/           workflows, pull-request template, CODEOWNERS   (must stay at the repository root)
```

- Code lives only in `4-Implementation/`. Run every command in this document from inside that folder unless it says otherwise.
- Documents live in the folder of their phase; one sub-folder per document so attachments (xlsx, pptx, images) can sit beside the text.
- File and folder names: English, no spaces in code folders, no accents, at most about 60 characters (Windows paths are limited).

## 2. Branches

- `main` is always working and is **protected**: no direct pushes, pull requests only, at least 1 approval (the Leader), the
  `CI/CD` check must pass once the workflow exists.
- One branch per piece of work, created from the latest `main`: `feature/<area>-<short-description>` (for example
  `feature/subscription-billing`), `fix/<short-description>`, `docs/<short-description>`.
- Delete the branch after the pull request is merged.

## 3. Commits

- Small, focused, in the imperative mood: `Add refund endpoint to the billing service`, not `fixed stuff`.
- Prefix with the area when it helps: `billing: make consume idempotent`, `docs: add RACI matrix`.
- One logical change per commit; do not mix a refactor with a feature; never commit generated or secret files.
- Use your real name and your GitHub e-mail so that the history shows who did what:
  `git config user.name "Your Name"` and `git config user.email "you@example.com"`.

## 4. Pull requests and reviews

- Open the pull request against `main`; fill in the template (what, why, how it was tested, which RTM ids it touches).
- Keep it reviewable: one area per pull request. A package push (your whole initial part) is the only exception.
- The Leader reviews and merges every pull request except his own, which Sayem reviews. If your files are co-owned (see `.github/CODEOWNERS`), the co-owner is asked to look too.
- Reply to every review comment; push fixes to the same branch; do not force-push after a review has started.
- Merge method: **merge commit** (keeps each member's own commits visible in the history).
- You never approve your own pull request.

## 5. Code rules (what the project already follows)

| Rule | Why |
|---|---|
| Python 3.12, 4-space indent, readable names, short comments that explain *why* | the whole codebase is written this way |
| A service lives in `services/<name>/tr_<name>/` and exposes `GET /healthz` and routes under `/v1/` | `tr_<name>` prevents module-name clashes; versioned routes let the API evolve (RTM NFR-11) |
| The website talks to services **only** through `core/services.py` and never imports a service package (only `tr_common`) | enforced by `BoundaryTests` in `core/tests.py` |
| Every call between services carries the `X-Service-Token` header | RTM NFR-05 |
| No service reads another service's database | database per service (RTM ARC-05) |
| Money and credits change only through the billing service, with an idempotency key | RTM NFR-08 |
| Configuration comes from environment variables, with defaults that work for development | `config/settings.py`, `.env.example` |
| Errors are JSON `{"error": ..., "message": ...}` with the right status code | RTM NFR-13 |
| Templates may use Tailwind classes; if you add a class that is not compiled yet, rebuild the CSS (`npm run build:css`) | `README.md` of `4-Implementation` |

## 6. Testing: what must pass before a pull request

Run from `4-Implementation/` (a virtual environment with `pip install -r requirements-dev.txt`):

```
python -m unittest discover -s services/tests -t services     # the 8 services on their own (65 tests)
python manage.py test                                         # the website with the services in-process (105 tests)
python manage.py makemigrations --check --dry-run             # models and migrations agree
```

- A new feature comes with a test in the file of its owner (see the file map in the RACI workbook).
- A bug fix comes with a test that fails without the fix.
- After a run, update the evidence in the RTM sheet *Test Cases* (result, date) and add the new test to *Test Links*.

## 7. Secrets and security

- **Never commit** `.env`, `db.sqlite3`, anything in `secrets/` (keys, JSON credentials), tokens, passwords, server addresses or
  personal e-mail addresses. The two `.gitignore`/`.dockerignore` files already refuse the usual ones; check `git status` anyway.
- If a secret reaches GitHub, treat it as public: **rotate it first** (new key, new password), then tell the Leader. Deleting
  the commit is not enough.
- GitHub Actions secrets (`AZURE_VM_HOST`, `AZURE_VM_USER`, `AZURE_VM_SSH_KEY`) are set in the repository settings by the
  deployment engineer, never in a file. The names are historical: they may point to any server.
- The server `.env` needs at least `INTERNAL_TOKEN`, `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` (see `.env.example`).

## 8. Documentation

- Every deliverable has an owner (RACI matrix). The owner keeps it current; a change to behaviour changes the document in the same pull request.
- Write for a team mate who has not seen the code: what it does, how to run it, what it does **not** do. Say honestly what has not been tested.
- Keep requirement ids (FR-xx, NFR-xx...) in the text so the RTM stays traceable.

## 9. Definition of done

A change is done when: the code and its test are merged; the tests above pass; the docs and the RTM are updated; the
owner and the reviewer agree in the pull request; nothing secret is in the diff.

## 10. Legacy comments

Some comments in the code still say *Member A*, *Member B* or *Member C* from the first plan: A = satellite / Earth Engine,
B = AI and machine learning, C = cloud storage and deployment. When you next edit such a file, replace the label with the
owner's name from the Staffing Plan.
