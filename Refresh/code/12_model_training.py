"""
NBA Game Outcome — Model Training & Evaluation
===============================================
Trains multiple classifiers on the feature-engineered dataset, evaluates each
with TimeSeriesSplit (season-aware), prints a comparison table, and saves the
best model as a .joblib file.

Models compared
---------------
    RidgeClassifier         (baseline, matches original notebook)
    LogisticRegression
    RandomForestClassifier
    GradientBoostingClassifier

Usage
-----
    python Refresh/code/12_model_training.py

Outputs
-------
    Refresh/data/models/best_model.joblib   — best model by mean CV accuracy
    Refresh/data/models/scaler.joblib       — fitted MinMaxScaler
    Refresh/data/models/selected_features.txt — feature names used by the model
"""

import os
import sys
import warnings
import time
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import RidgeClassifier, LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.feature_selection import SequentialFeatureSelector
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.join(os.path.dirname(SCRIPT_DIR), "data")

DATA_PATH   = os.path.join(BASE_DIR, "feature_engineered_csv", "season2date_with_nextGame_features.csv")
OUTPUT_DIR  = os.path.join(BASE_DIR, "models")

N_FEATURES_TO_SELECT = 40
CV_SPLITS = 3
RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# Columns that are not predictive features
# ---------------------------------------------------------------------------
NON_FEATURE_COLS = {
    "Season", "season", "date", "date_next", "won", "target",
    "team", "team_opp", "team_opp_next", "team_opp_next_rival",
    "team_x", "team_y", "team_rival",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_data(path: str) -> pd.DataFrame:
    print(f"Loading data from {path} ...")
    df = pd.read_csv(path, low_memory=False)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    print(f"  Loaded {len(df):,} rows, {df.shape[1]} columns")
    return df


def prepare_features(df: pd.DataFrame):
    """Return (X, y, feature_names, season_series)."""
    # Drop rows where target == 2 (last game of season — no next game)
    df = df[df["target"] != 2].copy()

    # Identify usable feature columns: numeric, not in exclusion set
    exclude = NON_FEATURE_COLS | {c for c in df.columns if df[c].dtype == object}
    feature_cols = [c for c in df.columns if c not in exclude and c != "target"]

    X = df[feature_cols].select_dtypes(include=[np.number])
    # Drop any columns that are entirely NaN
    X = X.dropna(axis=1, how="all")
    feature_cols = list(X.columns)

    # Fill remaining NaNs with column median
    X = X.fillna(X.median())

    y = df["target"].astype(int)

    # Keep season for stratified backtesting
    season_col = "Season" if "Season" in df.columns else "season"
    seasons = df[season_col] if season_col in df.columns else pd.Series(["all"] * len(df))

    print(f"  Features: {len(feature_cols)}, Samples: {len(X):,}")
    return X, y, feature_cols, seasons


# ---------------------------------------------------------------------------
# Feature selection
# ---------------------------------------------------------------------------
def select_features(X: pd.DataFrame, y: pd.Series, base_model, n: int, cv: int):
    """Return list of selected feature names."""
    print(f"\nRunning SequentialFeatureSelector (n={n}, cv={cv}) ...")
    t0 = time.time()
    sfs = SequentialFeatureSelector(
        base_model,
        n_features_to_select=n,
        direction="forward",
        cv=TimeSeriesSplit(n_splits=cv),
        n_jobs=-1,
    )
    sfs.fit(X, y)
    selected = list(X.columns[sfs.get_support()])
    print(f"  Done in {(time.time()-t0)/60:.1f} min  |  features: {selected}")
    return selected


# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------
def backtest(df_full: pd.DataFrame, model, feature_cols: list, seasons, start_idx: int = 2):
    """Season-by-season rolling train/test split (TimeSeriesSplit style)."""
    season_list = sorted(seasons.unique())
    all_preds = []

    for i in range(start_idx, len(season_list)):
        season = season_list[i]
        train_mask = seasons < season
        test_mask  = seasons == season

        X_train = df_full.loc[train_mask, feature_cols]
        y_train = df_full.loc[train_mask, "target"].astype(int)
        X_test  = df_full.loc[test_mask,  feature_cols]
        y_test  = df_full.loc[test_mask,  "target"].astype(int)

        if len(X_train) == 0 or len(X_test) == 0:
            continue

        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        combined = pd.DataFrame(
            {"actual": y_test.values, "prediction": preds},
            index=y_test.index,
        )
        combined["season"] = season
        all_preds.append(combined)

    return pd.concat(all_preds) if all_preds else pd.DataFrame()


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------
def get_models():
    return {
        "RidgeClassifier":          RidgeClassifier(alpha=1.0),
        "LogisticRegression":       LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "RandomForest":             RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1),
        "GradientBoosting":         GradientBoostingClassifier(n_estimators=100, random_state=RANDOM_STATE),
    }


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------
def evaluate_predictions(preds_df: pd.DataFrame, model_name: str) -> dict:
    if preds_df.empty:
        return {}
    y_true = preds_df["actual"]
    y_pred = preds_df["prediction"]
    acc    = accuracy_score(y_true, y_pred)
    print(f"\n{'='*60}")
    print(f"  {model_name}  —  overall accuracy: {acc:.4f}")
    print(f"{'='*60}")
    print(classification_report(y_true, y_pred))
    return {"model": model_name, "accuracy": acc}


def plot_confusion_matrix(preds_df: pd.DataFrame, model_name: str, output_dir: str):
    if preds_df.empty:
        return
    cm = confusion_matrix(preds_df["actual"], preds_df["prediction"])
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title(f"Confusion Matrix — {model_name}")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    path = os.path.join(output_dir, f"confusion_{model_name.replace(' ', '_')}.png")
    plt.savefig(path)
    plt.close()
    print(f"  Saved: {path}")


def plot_accuracy_comparison(results: list, output_dir: str):
    if not results:
        return
    df = pd.DataFrame(results).sort_values("accuracy", ascending=False)
    plt.figure(figsize=(8, 5))
    bars = plt.bar(df["model"], df["accuracy"], color="steelblue")
    plt.ylim(0.4, 0.8)
    plt.ylabel("Accuracy")
    plt.title("Model Accuracy Comparison")
    plt.xticks(rotation=15, ha="right")
    for bar, acc in zip(bars, df["accuracy"]):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                 f"{acc:.3f}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    path = os.path.join(output_dir, "model_comparison.png")
    plt.savefig(path)
    plt.close()
    print(f"\n  Saved comparison chart: {path}")


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------
def print_baseline(df: pd.DataFrame):
    home_win_rate = df[df["home"] == 1]["won"].mean() if "home" in df.columns else None
    print(f"\nBaseline — home team win rate: "
          f"{home_win_rate:.4f}" if home_win_rate is not None else "N/A")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- Load ----
    df = load_data(DATA_PATH)
    print_baseline(df)
    X, y, feature_cols, seasons = prepare_features(df)

    # Attach season + target back for backtesting
    season_col = "Season" if "Season" in df.columns else "season"
    bt_df = X.copy()
    bt_df["target"] = y
    bt_df["season"] = seasons.values

    # ---- Scale ----
    print("\nScaling features ...")
    scaler = MinMaxScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=feature_cols, index=X.index)
    bt_df_scaled = X_scaled.copy()
    bt_df_scaled["target"] = y.values
    bt_df_scaled["season"] = seasons.values

    # ---- Feature selection (using RidgeClassifier as selector estimator) ----
    n_select = min(N_FEATURES_TO_SELECT, len(feature_cols))
    selected = select_features(X_scaled, y, RidgeClassifier(), n_select, CV_SPLITS)

    # Save selected features
    feat_path = os.path.join(OUTPUT_DIR, "selected_features.txt")
    with open(feat_path, "w") as f:
        f.write("\n".join(selected))
    print(f"\n  Selected features saved to: {feat_path}")

    # ---- Train & evaluate all models ----
    models     = get_models()
    results    = []
    best_acc   = -1
    best_name  = None
    best_model = None

    for name, model in models.items():
        print(f"\n{'─'*60}")
        print(f"  Training: {name}")
        t0 = time.time()
        preds = backtest(bt_df_scaled, model, selected, bt_df_scaled["season"], start_idx=2)
        elapsed = time.time() - t0
        print(f"  Backtest completed in {elapsed:.1f}s")

        metrics = evaluate_predictions(preds, name)
        if metrics:
            results.append(metrics)
            plot_confusion_matrix(preds, name, OUTPUT_DIR)
            if metrics["accuracy"] > best_acc:
                best_acc   = metrics["accuracy"]
                best_name  = name
                best_model = model

    # ---- Summary ----
    if results:
        print(f"\n{'='*60}")
        print("  RESULTS SUMMARY")
        print(f"{'='*60}")
        summary = pd.DataFrame(results).sort_values("accuracy", ascending=False)
        print(summary.to_string(index=False))
        plot_accuracy_comparison(results, OUTPUT_DIR)

        # ---- Save best model ----
        if best_model is not None:
            # Re-fit best model on all available data
            best_model.fit(X_scaled[selected], y)
            model_path  = os.path.join(OUTPUT_DIR, "best_model.joblib")
            scaler_path = os.path.join(OUTPUT_DIR, "scaler.joblib")
            joblib.dump(best_model, model_path)
            joblib.dump(scaler, scaler_path)
            print(f"\n  Best model : {best_name}  (accuracy {best_acc:.4f})")
            print(f"  Saved to   : {model_path}")
            print(f"  Scaler     : {scaler_path}")


if __name__ == "__main__":
    main()
