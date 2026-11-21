## What does this pull request do?
Adds my part of TerraRisk AI: shared library, satellite service, Docker files, developer scripts and architecture documents. 31 new files, nothing changed or deleted.
RACI rows (responsible): D-01, D-06, I-16, I-17, I-18, I-19, T-01, T-03, T-04, O-03.

## Why?
This is the part of the project assigned to Sayem Md Sajjudul Islam (Docker engineer) in the RACI matrix (`1-Planning/Staffing-Plan/TerraRisk_RACI.xlsx`). The code was built and tested in the original project; this pull request moves it into the team repository.

## RTM requirement ids touched
FR-04, ARC-06, NFR-03, NFR-04, NFR-05, NFR-09, NFR-12, NFR-13, NFR-14, NFR-17, OPS-01, OPS-04, OPS-05, DOC-01, DOC-03, DOC-05

## How was it tested?
- [ ] `python -m unittest discover -s services/tests -t services`  (from `4-Implementation/`, after the shared library is on `main`)
- [ ] `python manage.py test`
- [ ] `python manage.py makemigrations --check --dry-run`
- [x] Files checked against `MANIFEST.csv` (names, sizes and SHA-256 hashes) before the commit
- [ ] Not applicable (documents only)

## Checklist
- [x] Only files of my own area are changed (see `.github/CODEOWNERS` and the *File Map* sheet of the RACI workbook)
- [x] No secrets in the diff: no `.env`, keys, databases, passwords, server addresses
- [ ] Documents and the RTM are updated if behaviour changed
- [x] The branch name follows the Project Standards (`feature/docker-satellite-common`)
