from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "processed" / "landslide_satellite_features.csv"
MODEL_FILE = ROOT / "services" / "risk" / "tr_risk" / "models" / "landslide_model.pkl"

FEATURES = ["ndvi", "lst_peak_c", "soil_moisture", "slope", "elevation"]
LABEL = "landslide"


def main():
    df = pd.read_csv(DATA_FILE)
    print(f"Rows: {len(df)}")
    print(df[LABEL].value_counts())

    X = df[FEATURES]
    y = df[LABEL]
    groups = df["event_id"] if "event_id" in df.columns else df["event_date"]

    models = {
        "Logistic regression": make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression()
        ),
        "Random forest": make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(n_estimators=300, min_samples_leaf=5, random_state=42),
        ),
    }

    best_name, best_auc = None, 0
    for name, model in models.items():
        scores = cross_val_score(model, X, y, groups=groups,
                                 cv=GroupKFold(n_splits=5), scoring="roc_auc")
        print(f"{name}: AUC = {scores.mean():.3f}")
        if scores.mean() > best_auc:
            best_name, best_auc = name, scores.mean()

    best = models[best_name].fit(X, y)
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": best, "features": FEATURES, "auc": best_auc}, MODEL_FILE)

    print(f"Best model: {best_name} (AUC {best_auc:.3f})")
    print(f"Saved to: {MODEL_FILE}")


if __name__ == "__main__":
    main()