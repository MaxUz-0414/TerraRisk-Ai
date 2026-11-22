# TerraRisk AI

Hyper-local climate and upstream-hazard analysis for farmers, home buyers and property investors: draw a parcel on a
satellite map and get a flood + landslide risk score, plain-language advice for your role, satellite pictures and a PDF
certificate. A Django website plus eight small services, run with Docker Compose.

This repository is the team project of six students. The folders follow the phases of the project:

```
terrarisk-ai/
├── 1-Planning/          System Request · Feasibility Analysis · Staffing Plan (RACI) · Project Standards · Risk Assessment
├── 2-Analysis/          Requirements and use cases · Requirements Traceability Matrix (RTM) · data and model analysis
├── 3-Design/            Architecture · integration · frontend · subscription · AI · Docker · deployment
├── 4-Implementation/    All source code (website, 8 services, tests, Docker files) - start with its README.md
└── .github/             CI/CD workflow, pull-request template, CODEOWNERS
```

## Team

| # | Member | Role | Branch |
|---|---|---|---|
| 1 | **Abduraimboy Murodullaev** (Leader) | Project Leader and web integration | `feature/leader-integration-planning` |
| 2 | **Anvarjon Gulomov** | Frontend developer | `feature/frontend-ui` |
| 3 | **Barsha Ghimire** | Subscription, billing and accounts developer | `feature/subscription-billing` |
| 4 | **Ramuna Sunwar** | AI / machine-learning engineer | `feature/ai-models` |
| 5 | **Sayem Md Sajjudul Islam** | Docker engineer | `feature/docker-satellite-common` |
| 6 | **Md Farhad Hossain** | Deployment (DevOps) engineer | `feature/deployment-cicd` |


Who owns which file or deliverable: [`1-Planning/Staffing-Plan/TerraRisk_RACI.xlsx`](1-Planning/Staffing-Plan/TerraRisk_RACI.xlsx)
(RACI matrix and file map) and [`.github/CODEOWNERS`](.github/CODEOWNERS).

## Start here

| I want to... | Go to |
|---|---|
| run the project on my laptop | [`4-Implementation/README.md`](4-Implementation/README.md) |
| understand how it is built and why | [`3-Design/README.md`](3-Design/README.md) and [`4-Implementation/ARCHITECTURE.md`](4-Implementation/ARCHITECTURE.md) |
| see what is required and whether it is proven | [`2-Analysis/`](2-Analysis/) (RTM) |
| push my own part | [`1-Planning/Project-Standards/Project-Standards.md`](1-Planning/Project-Standards/Project-Standards.md) |

## Rules in one paragraph

Nobody pushes to `main`. Everyone works on their own branch (`feature/...`), opens a pull request, the Leader reviews and
merges it. Never commit `.env`, keys, databases or anything in `secrets/` (the `.gitignore` files already refuse them).
Details are in the Project Standards.
