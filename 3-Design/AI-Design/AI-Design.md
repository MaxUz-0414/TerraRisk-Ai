# AI Design

| | |
|---|---|
| **Owner** | Ramuna Sunwar (AI). Accountable: Abduraimboy Murodullaev. Consulted: Anvarjon (results page), Sayem (satellite features, Docker image), Farhad (Gemini key on the server) |
| **Version / date** | 1.0, 19 November 2026 |
| **Code** | `4-Implementation/services/risk/`, `services/advisory/`, `services/chatbot/`, `ml/`, `data/`, `check_gemini.py` |
| **RTM** | FR-05, FR-06, FR-09, ML-01 to ML-04, NFR-15, NFR-16 |

The data, the training method and the honest numbers are in
[`2-Analysis/Data-and-Model-Analysis/Data-and-Model-Analysis.md`](../../2-Analysis/Data-and-Model-Analysis/Data-and-Model-Analysis.md).
This document is about how the AI parts are *built into* the system.

## 1. Three AI services, three different failure behaviours

| Service | What it does | If it fails |
|---|---|---|
| **risk** (stateless, reads model files) | score, hazard cards, persona view, headline, what-if scenarios | analysis fails, no credit used (critical) |
| **advisory** (stateless) | written advice for the persona | analysis still works; the advice box says it is missing (optional) |
| **chatbot** (own intent model) | help assistant and FAQ | the chat bubble apologises; the support page shows contact details |

Advisory is separate from risk because it calls an external LLM that is slow and sometimes down: a Gemini outage must
never remove the score.

## 2. The risk service

| Route | Purpose |
|---|---|
| `POST /v1/score` | features in → composite score (0 to 100), level, hazard cards |
| `POST /v1/view` | persona view: verdict, cards, factors ("why this score"), checklist, investor flags, scenarios |
| `GET /v1/model` | model status and the published metric (cross-validated AUC) |

Modules (`services/risk/tr_risk/`): `scoring.py` (composite score and cards), `ml.py` (loads `models/*.pkl`, clips inputs to
range, falls back to a transparent formula if a file is missing or broken), `risk.py` (levels and persona groups),
`persona_view.py`, `scenarios.py`, `headline.py`.

- **Composite score** = 0.5 × flood + 0.5 × landslide (`FLOOD_WEIGHT`, `LANDSLIDE_WEIGHT`). Without the landslide model, the flood score alone.
- **Levels**: low below 40, medium 40 to 64, high 65 and above.
- **Persona groups**: farmer, home buyer, investor (developer and analyst use the investor view).
- **Models are files inside the image** (read-only): to change a model, retrain with `ml/` and rebuild the risk image.

## 3. The advisory service

`POST /v1/advice` → four labelled lines (*Immediate Action*, *Action Item*, *Advisory*, *Advisory*).
With `GEMINI_API_KEY` set it asks Gemini; **on any error or empty answer it uses built-in templates**, and says which source
was used (`gemini` or `template`) so the results page can be transparent (NFR-15). The model name comes from `GEMINI_MODEL`
because Google retires model names; `check_gemini.py` tests the key and the model name from the command line.

## 4. The chatbot service

A small intent classifier, not a general AI: TF-IDF over character groups (typos still match), nearest example question
from `knowledge.py`, and a similarity threshold (0.34) below which the bot says it is not sure instead of guessing.
`POST /v1/chat`, `POST /v1/faq`. If `GEMINI_API_KEY` is set, an uncertain question may be passed to Gemini, restricted to the
knowledge text. The model is trained at image build time (`python -m tr_chatbot.train`), so the pickle is not stored in Git.

## 5. Training pipeline (`ml/`)

`prepare_landslide_data.py` → `build_dataset.py` (Earth Engine login needed) → `train_landslide_model.py` (spatial
cross-validation grouped by event) → `services/risk/tr_risk/models/landslide_model.pkl`; `train_model.py` → `hazard_model.pkl`.

## 6. Design rules

- A model file that is missing or broken must never take the site down: fall back, log, keep serving.
- Inputs are clipped to the training range before scoring.
- Say what a number is: *relative index, not probability*; *sensitivity, not forecast*.
- Every route is under `/v1`; every response is JSON; every call needs `X-Service-Token`.

## 7. Open items

Validate the flood model against real flood records (GAP-08); one live Gemini run with a real key (GAP-02); more landslide
events and features to raise the AUC (ML-02); the label-leak caveat for the flood model stays in every report.
