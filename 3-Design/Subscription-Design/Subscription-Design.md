# Subscription and Billing Design

| | |
|---|---|
| **Owner** | Barsha Ghimire (Subscription). Accountable: Abduraimboy Murodullaev. Consulted: Anvarjon (pricing and checkout pages), Sayem (volume and container), Farhad (revenue on the dashboard) |
| **Version / date** | 1.0, 19 November 2026 |
| **Code** | `4-Implementation/services/billing/`, `accounts/`, `services/report/`, `templates/pricing.html`, `checkout.html`, `profile.html`, `registration/` |
| **RTM** | FR-01, FR-07, FR-08, FR-12, FR-14, FR-15, FR-18, ARC-04, NFR-02, NFR-08, NFR-20 |

## 1. Plans

| Plan | Analyses | Price | Per analysis |
|---|---|---|---|
| Free (every new account) | 5 | $0 | n/a |
| Starter | 20 | $4.99 | $0.25 |
| Plus | 30 | $6.99 | $0.23 |
| Pro (most popular) | 50 | $9.99 | $0.20 |
| Business | 100 | $17.99 | $0.18 |
| Unlimited | unlimited for 30 days | $29.00 | n/a |

The plan list exists twice on purpose: `services/billing/tr_billing/plans.py` (the truth) and `accounts/plans.py` (the
website's built-in copy, so the pricing page still renders when billing is down). A test fails if they differ.

## 2. Two designs, one chosen

| | Design A: the website owns the balance | **Design B: a billing service owns the balance (chosen)** |
|---|---|---|
| For | one database transaction covers "create parcel" and "use one credit" | small surface, one writer, auditable ledger, replaceable by a real provider |
| Against | payment logic welded to the website; any bug can change balances | two databases: needs refund and idempotency; one more thing that can be down |

## 3. How Design B stays correct

1. **Reserve first, work second:** `AnalyzeView` calls `consume(key)` before the expensive analysis.
2. **Compensate:** a failed analysis or a failed save sends the same key to `refund`; a failed analysis costs nothing.
3. **Idempotency:** `ledger.idem_key` is `UNIQUE`; repeating a consume or refund changes the balance once.
4. **Billing is the source of truth:** `free_searches`, `plan_key`, `unlimited_until` on the website `User` are a cached copy refreshed after every billing call; editing the copy gives no free searches (tested).
5. **Fail closed:** billing unreachable → analysis and checkout are refused with "nothing was charged" (HTTP 503).
6. **First contact migration:** the first time the website talks to billing about an existing user it sends the old balance (`initial`).
7. **Demo payments:** `PAYMENTS_DEMO=True` records a purchase without charging anybody; with `False`, checkout answers 501 until a real provider is connected inside the billing service. No card data ever touches our code.

## 4. Data model (billing's own SQLite database, volume `billing_data`)

| Table | Columns |
|---|---|
| `accounts` | `user_id` (PK), `email`, `free_searches`, `unlimited_until`, `plan_key`, `created_at` |
| `purchases` | `id`, `user_id`, `plan_key`, `plan_name`, `searches`, `price`, `created_at` (index on user and id) |
| `ledger` | `id`, `user_id`, `delta`, `reason`, `idem_key` **UNIQUE**, `created_at` |

## 5. API of the billing service

`GET /v1/plans` · `PUT|GET /v1/accounts/<id>` · `POST /v1/accounts/<id>/consume` · `/refund` · `/checkout` · `GET /v1/stats`
(timeout 10 s; every call needs `X-Service-Token`).

## 6. Accounts (website)

Email is the username; a signup form with persona choice (`accounts/forms.py`, `personas.py`); every sign-in and failed
attempt is stored as a `LoginEvent` by a Django signal (`accounts/signals.py`) with the IP (from `CF-Connecting-IP` or
`X-Real-IP`, see `core/netutil.py`), and a background thread asks the geocode service for city and country so signing in
never waits. Private addresses are never sent outside.

## 7. PDF certificate (report service)

`POST /v1/reports` builds a multi-page PDF (score, factors, four satellite pictures fetched in parallel, hazard cards,
charts, scenarios, checklists, method and limits) with ReportLab and Pillow. Layout changes bump `REPORT_VERSION` in
`analysis/views.py` so older stored PDFs are rebuilt on the next download.

## 8. Open items

- Real payment provider (FR-18): connect inside `checkout` in `services/billing/tr_billing/app.py`; no card numbers in our code.
- Scope the idempotency key to (user, key) (DEF-02) and move billing to PostgreSQL before running several replicas (NFR-20).
- Back up `billing_data` together with PostgreSQL.
