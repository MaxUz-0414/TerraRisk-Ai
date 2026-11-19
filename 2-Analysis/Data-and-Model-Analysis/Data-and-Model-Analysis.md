# Data and Model Analysis

| | |
|---|---|
| **Owner** | Ramuna Sunwar (AI). Accountable: Abduraimboy Murodullaev. Consulted: Sayem (satellite features and Docker image) |
| **Version / date** | 1.0, 19 November 2026 |
| **Code** | `4-Implementation/ml/`, `4-Implementation/data/`, `4-Implementation/services/risk/tr_risk/` |

This is the honest description of what the models are, what data they use and how far the numbers can be trusted.
Requirements: ML-01, ML-02, ML-03, ML-04, NFR-16 in the RTM.

## 1. The score

The risk score shown to users is `0.5 × flood score + 0.5 × landslide score` (`FLOOD_WEIGHT`, `LANDSLIDE_WEIGHT` in
`scoring.py`). If the landslide model file is missing or broken, the flood score alone is used and the site keeps working.
Levels: low below 40, medium 40 to 64, high 65 and above.

## 2. Flood model (`ml/train_model.py`)

| | |
|---|---|
| Inputs (5, in this order) | upstream slope (°), distance to river (m), NDVI trend (%), peak land-surface temperature (°C), soil-moisture change (%) |
| Training data | 4,000 synthetic points drawn uniformly from realistic ranges |
| Labels | the rule-based formula `rule_based_score` plus Gaussian noise (σ = 4), clipped to 0 to 100 |
| Model | random forest regressor, 100 trees, depth 8 |
| Reported metric | R² on a 20 % hold-out set (printed by the script) |
| Output | `services/risk/tr_risk/models/hazard_model.pkl` |

**Limit, stated plainly:** the labels are made from a formula, so the model learns to imitate that formula. It is a working
prototype of the pipeline, **not** a validated flood predictor. Replace `make_dataset()` with sampled satellite features at
known flood locations to change that (RTM GAP-08, risk R-11).

## 3. Landslide model (`ml/prepare_landslide_data.py`, `ml/build_dataset.py`, `ml/train_landslide_model.py`)

**Data**

| Step | File | Content |
|---|---|---|
| raw | `data/raw/Global_Landslide_Catalog_Export_rows.csv` | NASA Global Landslide Catalog export: 11,033 rows, 31 columns |
| clean | `data/processed/landslide_events_clean.csv` | 11,000 events with date, latitude, longitude (missing or invalid rows removed) |
| features | `data/processed/landslide_satellite_features.csv` | 600 rows: 300 recorded landslides (label 1) and 300 random control points (label 0), events from 2007 to 2017 |

Each control point lies 10 to 50 km from its landslide and uses the same date; the two share an `event_id`.
Features per point are read from Google Earth Engine: NDVI (MODIS MOD13Q1), peak land-surface temperature (MODIS),
soil moisture (ERA5-Land), slope and elevation (SRTM, mean within 500 m). Missing values in the file: NDVI 32, temperature 33,
soil moisture 19, slope 1, elevation 1; they are filled with the median when training.

**Method**: 5-fold cross-validation with `GroupKFold` grouped by `event_id`, so a landslide and its own control points never
sit in different folds. Logistic regression and random forest are compared by ROC AUC; the better one is saved with its
feature list and AUC to `services/risk/tr_risk/models/landslide_model.pkl`.

**Results (from the project notes)**

| Run | Features | Logistic regression AUC | Random forest AUC |
|---|---|---|---|
| v1 (22 Oct 2026) | NDVI, temperature, soil moisture | 0.578 | 0.610 |
| v2 (4 Nov 2026) | v1 + slope, elevation | 0.632 | **0.704** (saved) |

Adding terrain features raised the AUC from about 0.61 to 0.70: moderate skill, suitable for a screening score.
The score is `100 × P(landslide)`, and because classes were balanced 1:1 by construction it is a **relative index, not a probability**.

**Limits**

- Control points are random nearby locations and are not verified as landslide-free.
- Small sample (600 rows); events are mostly 2007 to 2017.
- ERA5 soil moisture is coarse (about 11 km); SRTM covers 60° N to 56° S only.
- Rebuilding the feature file needs an Earth Engine login; the file in the repository was built earlier with credentials.

## 4. Persona views and scenarios (`persona_view.py`, `scenarios.py`, `headline.py`)

Not trained models: transparent rules computed from the stored features (drought, heat and runoff indices; what-if
scenarios such as summers 2 °C hotter, vegetation decline, soil that dries out). They show **sensitivity, not forecasts**
(RTM ML-04).

## 5. Written advice and the chatbot

- **Advisory service**: Gemini when `GEMINI_API_KEY` is set, otherwise built-in templates; any Gemini error falls back to the templates.
- **Chatbot**: a small intent classifier (TF-IDF over character groups, nearest example question, a similarity threshold below which it says it is not sure); about 8 in 10 fresh questions in the team's tests. Optional Gemini fallback limited to the knowledge text.

## 6. How to retrain

```
python ml/prepare_landslide_data.py      # raw catalogue -> clean events
python ml/build_dataset.py               # needs an Earth Engine login; writes the 600-row feature file
python ml/train_landslide_model.py       # prints the AUC of both models and saves the better one
python ml/train_model.py                 # flood model (formula labels)
docker compose up -d --build risk        # the risk image contains the model files
```

## 7. What a reader must not conclude

That the score is a forecast, an engineering opinion or an insurance rating; that the flood part has been checked against
real floods; or that the AUC of 0.70 applies outside the sampled regions and years.
