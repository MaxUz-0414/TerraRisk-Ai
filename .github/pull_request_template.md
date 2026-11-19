## What does this pull request do?
<!-- One or two sentences. Which area of the RACI matrix is it (for example I-09 Billing service)? -->

## Why?
<!-- The problem it solves or the requirement it covers. -->

## RTM requirement ids touched
<!-- For example FR-08, NFR-08. Write "none" for pure documentation. -->

## How was it tested?
- [ ] `python -m unittest discover -s services/tests -t services`  (from `4-Implementation/`)
- [ ] `python manage.py test`
- [ ] `python manage.py makemigrations --check --dry-run`
- [ ] Not applicable (documents only)

## Checklist
- [ ] Only files of my own area are changed (see `.github/CODEOWNERS` and the RACI file map)
- [ ] No secrets in the diff: no `.env`, keys, databases, passwords, server addresses
- [ ] Documents and the RTM are updated if behaviour changed
- [ ] The branch name follows the Project Standards
