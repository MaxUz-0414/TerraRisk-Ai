# Feasibility Analysis: TerraRisk AI

| | |
|---|---|
| **Owner** | Abduraimboy Murodullaev (Leader). Consulted: Barsha (economic), Ramuna (data), Sayem and Farhad (technical, operational) |
| **Version / date** | 1.0, 19 November 2026 |
| **Conclusion** | Feasible as a prototype that runs on one small server. Three items must be closed before it is called production-ready (section 5). |

The evidence used below comes from the repository and the RTM (`2-Analysis/Requirements/TerraRisk_RTM.xlsx`). "Evidence"
means a test that was run, not an opinion.

## 1. Technical feasibility

**Stack.** Python 3.12, Django (website, login, admin), Flask + gunicorn (eight services), PostgreSQL (website data),
SQLite (billing and geocode caches), scikit-learn (models), ReportLab (PDF), Leaflet + Esri imagery (map), Google Earth
Engine (real satellite data), Gemini (optional written advice), Docker Compose and nginx (deployment), GitHub Actions (CI).

| Question | Answer | Evidence |
|---|---|---|
| Can the work be split into services that fail independently? | Yes: website + 8 services, an orchestrator decides which steps are critical and which optional | RTM ARC-01, ARC-02, NFR-01; the degrade matrix in `ARCHITECTURE.md` section 6 |
| Can a credit never be lost or charged twice? | Yes, by design: billing owns a ledger with a unique idempotency key; refund on failure; fail closed when billing is down | RTM ARC-04, NFR-02, NFR-08; billing tests |
| Does the risk model work? | Moderately: landslide AUC about 0.70 (5-fold cross-validation grouped by event); flood model is a formula-labelled prototype | `2-Analysis/Data-and-Model-Analysis/`; RTM ML-01, ML-02, NFR-16 |
| Does the code run without any account or key? | Yes: demo data mode and in-process mode need nothing | `4-Implementation/README.md` |
| Are the pieces tested? | 65 service tests (run and passing), 105 website tests (recorded passing), 22 end-to-end checks (21 pass; the one failure is a test-script defect, DEF-01) | RTM sheets *Test Cases* and *Defects & Gaps* |
| What has never been run against the real thing? | Earth Engine, Esri/Google tiles, Nominatim, ipwho.is, a real browser drawing the maps, and the 11-container image build | RTM GAP-02, GAP-03, GAP-04 |

**Technical risks** are listed with owners in [`../Risk-Assessment/Risk-Assessment.md`](../Risk-Assessment/Risk-Assessment.md).

## 2. Operational feasibility

| Question | Answer |
|---|---|
| Who uses it? | Visitors and signed-in users (three personas) and the administrators (staff users) |
| Is it easy to use? | Guided flow: search a place, draw a parcel, press *Run AI Diagnosis*; the results page is written per persona; a help chatbot and a support page exist |
| Who runs it? | The deployment engineer (Farhad) with the Docker engineer (Sayem): see `3-Design/Deployment-Design/Deployment-Design.md` |
| What does the administrator see? | The admin dashboard: users, growth, where users sign in from, most searched places, risk mix, revenue, live service health, server load, events |
| What happens when something fails? | The user gets a clear message and is not charged; the admin sees an error event and a red service row |
| Backups | Billing balances live in the `billing_data` volume and website data in PostgreSQL: both must be backed up together (`4-Implementation/README.md`). A scheduled backup is **not** set up yet (risk R-10) |

## 3. Economic feasibility

*Costs below are the cost drivers found in the project. The amounts are for the team to fill in with real quotes; none are
invented here.*

| Cost driver | Needed for | Monthly amount |
|---|---|---|
| Virtual server (the live site runs on a small cloud server, 1 GB RAM, shared with other sites) | hosting 11 containers | *[to fill in]* |
| Domain name and DNS | the public address | *[to fill in]* |
| Google Earth Engine | real satellite data (free for non-commercial use; a licence is needed for commercial use) | *[to fill in]* |
| Gemini API | written advice (optional; templates are used without it) | *[to fill in]* |
| Google Map Tiles API | optional: Google place names instead of Esri labels | *[to fill in]* |
| Payment provider fees | real payments (not implemented yet) | *[to fill in]* |
| Team time | six students, one semester | not charged |

| Revenue driver | Value |
|---|---|
| Plans | Starter $4.99 / 20 analyses, Plus $6.99 / 30, Pro $9.99 / 50, Business $17.99 / 100, Unlimited $29.00 for 30 days |
| Price per analysis | Starter $0.25, Plus $0.23, Pro $0.20, Business $0.18 |
| Free searches | 5 per new account (a cost with no revenue: count it in the model) |

**Break-even** (to complete when the costs are known): monthly fixed cost divided by the average revenue per paying user,
adjusted for the free searches and the share of visitors who pay.

## 4. Schedule and organisational feasibility

- Six members, each with a clear area (RACI matrix, `1-Planning/Staffing-Plan/`); the Leader reviews every pull request.
- The code already exists and is tested; what remains is organisation (each member pushes and documents their own part),
  closing the open items in the RTM, and the real-world runs.
- *[to fill in: milestone dates from the course schedule]*

## 5. Conclusion and conditions

The project is **technically and operationally feasible** as a prototype. Before it is described as production-ready:

1. run the 11-container build on a real Docker host and close RTM GAP-03 (owner: Sayem);
2. run the Earth Engine path with real credentials once and close GAP-02 (owners: Sayem, Ramuna);
3. connect a real payment provider or state clearly that checkout is a demo (FR-18, owner: Barsha).
