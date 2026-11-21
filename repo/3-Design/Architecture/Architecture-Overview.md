# Architecture Overview

| | |
|---|---|
| **Owner** | Sayem Md Sajjudul Islam. Accountable: Abduraimboy Murodullaev |
| **Full text** | [`4-Implementation/ARCHITECTURE.md`](../../4-Implementation/ARCHITECTURE.md) (10 sections) · presentation: [`TerraRisk_Architecture.pptx`](TerraRisk_Architecture.pptx) |

TerraRisk started as one Django project (a monolith). It is now **a website plus eight small services**, split with the
disaggregation method from the cloud-computing lectures: find the functional boundaries, give each its own process, API and
data, and keep one place that owns the user interface.

```
 internet -> proxy (nginx, the only published port)
               -> web (Django: pages, login, admin, PostgreSQL)  --HTTP+JSON, X-Service-Token-->
                    analysis (orchestrator) -> satellite, risk, advisory, geocode
                    report (PDF) -> satellite          billing (credits, ledger)
                    geocode        chatbot             risk
```

| Service | Job | Owns |
|---|---|---|
| web | the only thing a browser talks to: UI, login, admin, parcels | users, parcels, logs (PostgreSQL) |
| analysis | one call fans out to satellite, risk, advisory, geocode | nothing |
| satellite | Earth Engine features and pictures | picture cache |
| risk | flood + landslide models, score, persona view, scenarios | model files |
| advisory | written advice (Gemini or templates) | nothing |
| report | PDF certificate | nothing |
| billing | accounts, credits, purchases, ledger | its own SQLite database |
| geocode | place search, reverse geocoding, IP location | answer cache |
| chatbot | help assistant | intent model |

Principles: cut where failure behaviour, data or rate of change differ; every API under `/v1`; every call carries a shared
token; database per service; billing fails closed; every service has `/healthz` and `/v1/info`; the same code runs in-process,
as separate processes, or in containers.

Read next: the degrade matrix (`ARCHITECTURE.md` section 6) and the two payment designs (section 4).
