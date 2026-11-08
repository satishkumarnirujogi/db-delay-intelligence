"""Weekly: train the delay model on logged point-in-time features; promote only if it beats the baseline.
    python -m ml.train

shortcut: trains on ml.feature_log in the database (last 60 days). Older history is in Parquet
(bronze/history/feature_log/); add it here if 60 days ever proves too little.
"""
from datetime import UTC, datetime, timedelta

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, precision_score, recall_score, roc_auc_score

from ingestion import loader
from ml.model import FEATURES, LATE_MIN, prepare, save_champion
from ml.score import LABEL

MIN_TEST_ROWS = 500
PARAMS = {"n_estimators": 400, "learning_rate": 0.05, "num_leaves": 31, "min_child_samples": 50,
          "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8, "random_state": 42, "verbose": -1}

LOAD = f"""
select {", ".join(FEATURES)}, planned_dep, actual_delay_min
from ml.feature_log
where labeled_at is not null and not actual_cancelled and actual_delay_min is not null
"""

INSERT_RUN = """
insert into ml.model_runs (model_version, train_rows, test_rows, test_from, mae_model, mae_baseline,
  mae_persistence, auc_model, auc_baseline, precision_late, recall_late, promoted, note)
values (%(model_version)s, %(train_rows)s, %(test_rows)s, %(test_from)s, %(mae_model)s, %(mae_baseline)s,
  %(mae_persistence)s, %(auc_model)s, %(auc_baseline)s, %(precision_late)s, %(recall_late)s,
  %(promoted)s, %(note)s)
"""


def time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Test = the most recent 7 days, or the last quarter of the history while it is shorter than 4 weeks.
    Never shuffled: the model must work on days it has not seen."""
    span = df["planned_dep"].max() - df["planned_dep"].min()
    test_from = df["planned_dep"].max() - min(timedelta(days=7), span / 4)
    return df[df["planned_dep"] < test_from], df[df["planned_dep"] >= test_from]


def baseline(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Median delay and share late per station x hour x train category (global value if unseen)."""
    keys = ["eva", "hour_of_day", "train_category"]
    g = train.assign(late=train["actual_delay_min"] >= LATE_MIN).groupby(keys, dropna=False).agg(
        med=("actual_delay_min", "median"), share=("late", "mean")).reset_index()
    m = test[keys].merge(g, on=keys, how="left")
    return (m["med"].fillna(train["actual_delay_min"].median()).to_numpy(),
            m["share"].fillna((train["actual_delay_min"] >= LATE_MIN).mean()).to_numpy())


def fit(df: pd.DataFrame) -> tuple[lgb.LGBMRegressor, lgb.LGBMClassifier]:
    x = prepare(df)
    # L1 objective predicts the median: robust to the long tail of very late trains
    reg = lgb.LGBMRegressor(objective="regression_l1", **PARAMS).fit(x, df["actual_delay_min"])
    clf = lgb.LGBMClassifier(**PARAMS).fit(x, df["actual_delay_min"] >= LATE_MIN)
    return reg, clf


def evaluate(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    reg, clf = fit(train)
    xt, y = prepare(test), test["actual_delay_min"].to_numpy()
    late = y >= LATE_MIN
    pred, p_late = reg.predict(xt), clf.predict_proba(xt)[:, 1]
    base_med, base_share = baseline(train, test)
    two_classes = late.any() and not late.all()
    return {
        "train_rows": len(train), "test_rows": len(test), "test_from": test["planned_dep"].min(),
        "mae_model": float(mean_absolute_error(y, pred)),
        "mae_baseline": float(mean_absolute_error(y, base_med)),
        "mae_persistence": float(mean_absolute_error(y, test["current_delay_min"].fillna(0))),
        "auc_model": float(roc_auc_score(late, p_late)) if two_classes else None,
        "auc_baseline": float(roc_auc_score(late, base_share)) if two_classes else None,
        "precision_late": float(precision_score(late, p_late >= 0.5, zero_division=0)),
        "recall_late": float(recall_score(late, p_late >= 0.5, zero_division=0)),
    }


def decide(m: dict) -> tuple[bool, str]:
    if m["test_rows"] < MIN_TEST_ROWS:
        return False, f"only {m['test_rows']} test rows (< {MIN_TEST_ROWS})"
    if m["mae_model"] >= m["mae_baseline"]:
        return False, "does not beat the station x hour x category baseline"
    note = "beats baseline"
    if m["mae_model"] >= m["mae_persistence"]:
        note += "; not yet better than 'stays as late as now'"
    return True, note


def main() -> None:
    version = f"{datetime.now(UTC):%Y%m%d-%H%M}"
    with loader.connect() as conn:
        with conn.transaction():
            conn.execute(LABEL)
        cur = conn.execute(LOAD)
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        if len(df) < 2 * MIN_TEST_ROWS:
            print(f"train: only {len(df)} labeled rows, skipping")
            return
        df["planned_dep"] = pd.to_datetime(df["planned_dep"], utc=True)

        train, test = time_split(df)
        m = evaluate(train, test)
        promoted, note = decide(m)
        print(f"train {m['train_rows']} / test {m['test_rows']} rows | MAE model {m['mae_model']:.2f} "
              f"baseline {m['mae_baseline']:.2f} persistence {m['mae_persistence']:.2f} | "
              f"AUC model {m['auc_model']} baseline {m['auc_baseline']} | {note}")

        if promoted:
            reg, clf = fit(df)  # refit on all labeled rows, so the newest week is included
            save_champion(reg.booster_, clf.booster_, {"model_version": version, "features": FEATURES, **m})
            print(f"promoted {version}")
        with conn.transaction():
            conn.execute(INSERT_RUN, {"model_version": version, "promoted": promoted, "note": note, **m})


if __name__ == "__main__":
    main()
