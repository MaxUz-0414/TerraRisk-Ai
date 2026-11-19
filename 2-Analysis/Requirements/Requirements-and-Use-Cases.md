# Requirements and Use Cases

| | |
|---|---|
| **Owner** | Abduraimboy Murodullaev (Leader). Consulted: every member for the requirements they own |
| **Version / date** | 1.0, 19 November 2026 |
| **Companion** | [`TerraRisk_RTM.xlsx`](TerraRisk_RTM.xlsx): the same requirements with design, code, tests, results and status |

Priorities use MoSCoW (Must, Should, Could). *Status* is the implementation status; *Responsible* is the member who answers for the requirement and *Consulted* the members who must be asked (the RACI workbook has the same data on its *Requirements* sheet). Whether a requirement is proven by tests is in the RTM, not here.

## Functional requirements

| ID | Requirement | The system shall... | Priority | Status | Responsible | Consulted |
|---|---|---|---|---|---|---|
| FR-01 | Register, sign in, choose a persona | A visitor shall be able to create an account with an email address, sign in and out, and choose a persona (user group) that shapes the results. | Must | Implemented | Barsha | Anvarjon |
| FR-02 | Search a place; map shows place names | A signed-in user shall be able to search for any place by name and see place names (labels) on the satellite map. | Must | Implemented | Abduraimboy | Anvarjon |
| FR-03 | Draw a polygon or pin with a hazard buffer | A user shall be able to draw a polygon or drop a pin on the map and choose a 3 to 5 km hazard buffer; invalid geometry shall be rejected. | Must | Implemented | Anvarjon | Abduraimboy |
| FR-04 | Satellite features and pictures | The system shall collect satellite-derived features (slope, river distance, vegetation, heat, soil moisture, rainfall ...) and four 1600x1000 pictures (true colour, vegetation, heat, water) for a parcel. | Must | Implemented | Sayem | Abduraimboy, Ramuna |
| FR-05 | Risk score, hazard cards, persona view, scenarios | The system shall compute a 0-100 composite risk score with hazard cards, a persona-specific view and what-if scenarios (investor group only). | Must | Implemented | Ramuna | Abduraimboy, Anvarjon |
| FR-06 | Persona-specific written advice | The system shall write advice for the user's persona with Gemini, and fall back to built-in templates (and say so) when no key or no answer is available. | Should | Implemented | Ramuna | Abduraimboy |
| FR-07 | PDF certificate with satellite pictures | A user shall be able to download a multi-page PDF certificate (score, factors, four satellite pictures, hazards, charts, scenarios, checklists, limits); the PDF shall be cached. | Should | Implemented | Barsha | Sayem |
| FR-08 | Search credits: free searches, consume, refund | Every account shall have free searches; each analysis shall use one search, a failed analysis shall give it back, and a user with no searches left shall be blocked. | Must | Implemented | Barsha | Abduraimboy |
| FR-09 | Help chatbot | The system shall answer common questions in a chat assistant (pricing, how to start, own balance), decline off-topic input and suggest alternatives. | Should | Implemented | Ramuna | Anvarjon |
| FR-10 | Admin dashboard | Staff shall see users, growth, sign-in locations, most searched and analysed places, risk mix, revenue, live service health and events in the Django admin; other users shall not. | Should | Implemented | Farhad | Anvarjon, Barsha |
| FR-11 | Saved parcels: list, open, delete | A user shall see only their own saved parcels, open a result page for each and delete a parcel. | Must | Implemented | Abduraimboy | Anvarjon |
| FR-12 | Profile update | A signed-in user shall be able to change their first name and persona on the profile page. | Could | Implemented | Barsha | Anvarjon |
| FR-13 | Landing and home pages | Visitors shall see a landing page with persona cards, team section and footer; signed-in users shall see a home page (how to start, recent analyses, balance) instead of the sign-up marketing. | Should | Implemented | Anvarjon | Abduraimboy |
| FR-14 | Pricing page and checkout | The system shall list the plans, let a signed-in user buy credits or an unlimited period (demo payments), record the purchase and extend an unlimited period when bought again. | Must | Implemented | Barsha | Anvarjon, Abduraimboy |
| FR-15 | Record sign-in location | The system shall store every sign-in and failed attempt with the visitor IP and a city/country guess, without ever making sign-in wait or fail. | Should | Implemented | Barsha | Farhad, Abduraimboy |
| FR-16 | Support page with FAQ | The support page shall list the FAQ from the chatbot service and still show contact details when the chatbot is down. | Could | Implemented | Anvarjon | Ramuna |
| FR-17 | Open results saved by older versions | Parcels saved by the old monolith (no snapshot, place or data mode) shall still open; missing parts are rebuilt on first view and old PDFs are rebuilt. | Should | Implemented | Abduraimboy | Ramuna |
| FR-18 | Real payment provider | Checkout shall charge a real card through a payment provider connected inside the billing service; card data shall never touch TerraRisk code. | Could | Planned | Barsha | Abduraimboy, Farhad |

## Architecture requirements

| ID | Requirement | The system shall... | Priority | Status | Responsible | Consulted |
|---|---|---|---|---|---|---|
| ARC-01 | Disaggregate the monolith: website + 8 services | The system shall be one website plus eight single-purpose services (analysis, satellite, risk, advisory, report, billing, geocode, chatbot), cut where failure, data or rate of change differ. | Must | Implemented | Abduraimboy | Sayem |
| ARC-02 | Analysis orchestrator with critical / optional steps | One call from the website shall fan out to satellite, risk, advisory and geocode; satellite and risk are critical, advisory and geocode are optional and reported as 'degraded'. | Must | Implemented | Abduraimboy | Sayem, Ramuna |
| ARC-03 | Single gateway between web and services | Web code shall reach services only through core/services.py, which turns HTTP answers into plain results or two exceptions (Unavailable, Rejected); web code shall never import a service's own package. | Must | Implemented | Abduraimboy | Sayem |
| ARC-04 | Payment Design B: billing owns the balance | Billing shall own balances in its own database with an append-only ledger; the web User columns are a cached copy; the first contact passes the balance the user already had. | Must | Implemented | Barsha | Abduraimboy |
| ARC-05 | Database per service | Each data owner shall keep its own data (web: Postgres; billing: SQLite; geocode: SQLite cache; satellite: picture files; risk: model files) and no service shall read another's database. | Must | Implemented | Abduraimboy | Barsha, Sayem |
| ARC-06 | Same code, two transports | The same Flask apps shall run in-process (no sockets) and as separate HTTP processes through the same client class, so the modes cannot drift apart. | Should | Implemented | Sayem | Abduraimboy |

## Data and machine-learning requirements

| ID | Requirement | The system shall... | Priority | Status | Responsible | Consulted |
|---|---|---|---|---|---|---|
| ML-01 | Flood hazard model | A flood hazard model shall be trained from the project dataset and shipped as a model file read by the risk service. | Should | Implemented | Ramuna | Sayem |
| ML-02 | Landslide model (spatial cross-validation) | A landslide model shall be trained with spatially grouped cross-validation (GroupKFold) and its AUC reported honestly (v1 RF 0.610 / LR 0.578; v2 RF 0.704 / LR 0.632). | Should | Implemented | Ramuna | Sayem |
| ML-03 | Composite score = 50% flood + 50% landslide | The risk score shall combine the flood and landslide models with equal weights (0.5 / 0.5) into a 0-100 value and return the parts. | Must | Implemented | Ramuna | Abduraimboy |
| ML-04 | Persona views are rule-based indices | Persona-specific 'what matters for you' bars, headline and scenarios shall be computed by transparent rules, not by a black-box model. | Should | Implemented | Ramuna | Anvarjon |

## Non-functional requirements

| ID | Requirement | The system shall... | Priority | Status | Responsible | Consulted |
|---|---|---|---|---|---|---|
| NFR-01 | Graceful degradation | A failing optional dependency (advisory, geocode, report, chatbot) shall remove only its own part of a page; a failing critical one (satellite, risk, billing, analysis) shall fail clearly with no credit used. | Must | Implemented | Abduraimboy | Sayem |
| NFR-02 | Billing fails closed | If billing cannot be reached, analysis and checkout shall be refused with 'nothing was charged' (HTTP 503); free analyses shall never be handed out because a service is down. | Must | Implemented | Barsha | Abduraimboy |
| NFR-03 | Bounded latency | Every service call shall have a timeout (analysis 170, satellite 130, report 120, advisory 30, chatbot 25, risk 15, geocode 10, billing 10 seconds); answers that repeat shall come from caches. | Should | Implemented | Sayem | Abduraimboy |
| NFR-04 | Retry once and circuit breaker | A GET shall be retried once; after 5 failures in a row the circuit shall open for 15 seconds so calls fail instantly instead of piling up behind a dead service. | Should | Implemented | Sayem | Abduraimboy |
| NFR-05 | Service-to-service authentication | Every service route except /healthz shall require the X-Service-Token; only the proxy shall publish a port; compose shall refuse to start without INTERNAL_TOKEN. | Must | Implemented | Sayem | Farhad |
| NFR-06 | Access control | Private pages shall require login, users shall never see another user's parcels, and only staff shall open the admin dashboard. | Must | Implemented | Abduraimboy | Farhad, Barsha |
| NFR-07 | Privacy and third-party limits | Private/local IP addresses shall never be sent to outside services, place search and chat shall be rate limited, no card data shall enter our code, and live payments shall stay off until a provider is connected. | Must | Implemented | Abduraimboy | Barsha |
| NFR-08 | Money integrity: idempotent consume and refund | Sending the same consume or refund twice (a retry after a timeout) shall change the balance once; a refund shall work only once and only for a search that was really charged. | Must | Implemented | Barsha | Abduraimboy |
| NFR-09 | Observability | Every service shall expose /healthz and /v1/info, log one JSON line per request with an X-Request-ID that is passed on, and the admin dashboard shall show each service live (a dead service shown, not an error). | Should | Implemented | Sayem | Farhad |
| NFR-10 | Testability at three levels | Each service shall be testable alone, the website with services in-process, and the whole stack over real HTTP. | Should | Implemented | Abduraimboy | Sayem |
| NFR-11 | Modifiability through versioned contracts | Each service shall keep its own versioned API (/v1) and its contract shall be guarded by tests (plans match, layer names exist, no cross-service imports). | Should | Implemented | Abduraimboy | Sayem |
| NFR-12 | Independent scaling | Heavy parts (PDF, satellite, models) shall run as stateless or single-writer services in their own container, scalable by running more containers. | Should | Implemented | Sayem | Farhad |
| NFR-13 | Consistent, safe error handling | Every service shall answer errors as JSON {error, message} with a proper status (400, 401, 404, 502, 503), validate input, and never leak internals. | Must | Implemented | Sayem | Abduraimboy |
| NFR-14 | Portability across run modes | The same code shall run in-process (laptop, tests), as separate processes (no Docker) and in containers. | Should | Implemented | Sayem | Farhad |
| NFR-15 | Transparency about data mode and limits | Results shall say when advice comes from templates or when data is demo data, and the documents shall list what was not verified and that scores are screening indices. | Should | Implemented | Ramuna | Abduraimboy |
| NFR-16 | Model quality is measured and published | Model quality shall be measured with spatially grouped cross-validation and published with the model (landslide AUC about 0.70); the flood model's label source shall be disclosed. | Should | Implemented | Ramuna | Abduraimboy |
| NFR-17 | Asynchronous jobs for slow work | Slow work (PDF building, satellite queries) shall run as jobs with a job id and polling so no user waits inside a request. | Could | Planned | Sayem | Abduraimboy, Barsha |
| NFR-18 | Per-service metrics and distributed tracing | Dashboards per service and tracing beyond the request id shall exist. | Could | Planned | Farhad | Sayem |
| NFR-19 | mTLS or a service mesh | If services ever run on several hosts, service traffic shall be encrypted and mutually authenticated. | Could | Planned | Farhad | Sayem |
| NFR-20 | Billing on Postgres for several replicas | Billing shall be able to run with more than one replica by moving its store from SQLite to Postgres. | Could | Planned | Barsha | Sayem |

## Operations requirements

| ID | Requirement | The system shall... | Priority | Status | Responsible | Consulted |
|---|---|---|---|---|---|---|
| OPS-01 | Container deployment (11 containers) | docker-compose shall define proxy, web, db and the 8 services on two networks (edge, backend); each service shall have a health check, a restart policy and log rotation. | Must | Implemented | Sayem | Farhad |
| OPS-02 | CI/CD pipeline | On push to main the pipeline shall run service tests, web tests, makemigrations --check and docker compose config, and deploy only if they pass. | Should | Implemented | Farhad | Sayem |
| OPS-03 | Reverse proxy | An nginx proxy shall serve static files with gzip and cache headers and pass the visitor's real IP (X-Real-IP, CF-Connecting-IP) to the website. | Should | Implemented | Farhad | Sayem |
| OPS-04 | Run everything without Docker | One command shall start the 8 services as local processes on ports 8101-8108 and print the environment lines the website needs. | Should | Implemented | Sayem | Abduraimboy |
| OPS-05 | One-command end-to-end check | One command shall check a running stack over real HTTP (health, analysis, pictures, PDF, billing, geocode, chatbot, optionally the website) and exit 1 on a failure; it shall be safe to run again. | Should | Implemented | Sayem | Abduraimboy |
| OPS-06 | Live deployment | The platform shall be reachable at https://terrarisk.sellovateai.com behind HTTPS. | Should | Partial | Farhad | Sayem |
| OPS-07 | Repository layout and workflow | The code shall live in one Git repository with the phase layout 1-Planning, 2-Analysis, 3-Design, 4-Implementation, one branch and pull request per member, CODEOWNERS ready to enable and the CI workflow at the repository root. | Must | Implemented | Abduraimboy | Sayem, Farhad |

## Documentation requirements

| ID | Requirement | The system shall... | Priority | Status | Responsible | Consulted |
|---|---|---|---|---|---|---|
| DOC-01 | Architecture document | ARCHITECTURE.md shall explain the picture, the disaggregation, the granularity question, the payment designs, communication, degradation, deployment, testing and honest limits. | Must | Implemented | Sayem | Abduraimboy |
| DOC-02 | README: setup, run and test | README shall explain how to run on a laptop (no Docker), as separate services, with Docker, and how to run the tests. | Must | Implemented | Abduraimboy | Sayem |
| DOC-03 | Architecture presentation | A slide deck shall present the problem, the monolith, the disaggregation method, the target architecture, quality and operations, and the evaluation. | Must | Implemented | Sayem | Abduraimboy |
| DOC-04 | Requirements traceability matrix | This workbook shall link every requirement to its design element, code, tests and results, and show gaps. | Must | Implemented | Abduraimboy | Sayem |
| DOC-05 | Honest-limits statement | What was not verified (real providers, container build, real-browser maps) and the limits of the scores shall be written down. | Must | Implemented | Sayem | Abduraimboy |
| DOC-06 | Team roster and roles | Names, student IDs and roles of the team shall be shown on the landing page and on the title slide. | Should | Implemented | Anvarjon | Abduraimboy, Sayem |
| DOC-07 | RACI matrix and file ownership | Every deliverable shall have exactly one accountable and at least one responsible member, and every file of the repository shall have exactly one owner, so the team can see who owns what. | Must | Implemented | Abduraimboy | Sayem |
| DOC-08 | Planning, analysis and design documents | The repository shall hold a System Request, Feasibility Analysis, Staffing Plan, Project Standards, Risk Assessment, the requirements, and one design document for each area. | Must | Partial | Abduraimboy | Sayem, Ramuna |

## Use cases

| ID | Use case | Actor |
|---|---|---|
| UC-1 | Sign up and choose a persona | Visitor |
| UC-2 | Find a place on the map | User |
| UC-3 | Draw a parcel and run an analysis | User |
| UC-4 | Read the score, advice and satellite pictures | User |
| UC-5 | Download the PDF certificate | User |
| UC-6 | Buy search credits | User |
| UC-7 | Ask the help chatbot | Visitor / User |
| UC-8 | Monitor and administer the platform | Admin |
| UC-9 | Deploy and operate the system | Team / Operator |
| UC-10 | Manage saved parcels and profile | User |
