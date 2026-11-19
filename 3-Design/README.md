# 3-Design

How TerraRisk AI is built and why. One design document per area, written by the member who owns that area, plus the
architecture overview and presentation.

| Document | Area | Owner |
|---|---|---|
| [`Architecture/Architecture-Overview.md`](Architecture/Architecture-Overview.md) | The whole system on two pages; links to the full `ARCHITECTURE.md` | Sayem |
| [`Architecture/TerraRisk_Architecture.pptx`](Architecture/TerraRisk_Architecture.pptx) | The 35-slide architecture presentation | Sayem |
| [`Integration-Design/Integration-Design.md`](Integration-Design/Integration-Design.md) | The website as a gateway, the analysis orchestrator, API contracts, website data | Abduraimboy |
| [`Frontend-Design/Frontend-Design.md`](Frontend-Design/Frontend-Design.md) | Pages, map, results page, styles, admin dashboard interface | Anvarjon |
| [`Subscription-Design/Subscription-Design.md`](Subscription-Design/Subscription-Design.md) | Plans, credits, the billing ledger, accounts, the PDF certificate | Barsha |
| [`AI-Design/AI-Design.md`](AI-Design/AI-Design.md) | Models, persona views, advice, chatbot | Ramuna |
| [`Docker-Design/Docker-Design.md`](Docker-Design/Docker-Design.md) | Containers, networks, volumes, health, the satellite service, the shared library | Sayem |
| [`Deployment-Design/Deployment-Design.md`](Deployment-Design/Deployment-Design.md) | Server, HTTPS, environment, CI/CD, runbook | Farhad |

The authoritative technical description is `4-Implementation/ARCHITECTURE.md`; these documents explain each area for its
reader and point to the files. If they disagree, the code wins and the document must be fixed.
