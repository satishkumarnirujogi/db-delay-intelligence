"""Shared by train.py and score.py: feature list, data prep, champion model save/load."""
import gzip
import json
import os
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from ingestion import storage

CATEGORICAL = ["eva", "train_category", "line"]
NUMERIC = [
    "minutes_to_departure", "current_delay_min", "has_realtime", "station_avg_delay_30m",
    "station_cancellations_60m", "upstream_delay_min", "hour_of_day", "iso_weekday",
    "temperature_c", "precipitation_mm", "snowfall_cm", "wind_gust_kmh",
]
FEATURES = CATEGORICAL + NUMERIC
LATE_MIN = 6  # DB definition: 6+ minutes late is not punctual

BUCKET = "ml"
CHAMPION = "champion"


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Same transformation for training and scoring. Blanks stay NaN (LightGBM handles them)."""
    x = df[FEATURES].copy()
    for c in CATEGORICAL:
        x[c] = x[c].astype("string").astype("category")
    for c in NUMERIC:
        x[c] = pd.to_numeric(x[c], errors="coerce").astype("float64")
    return x


def save_champion(regressor: lgb.Booster, classifier: lgb.Booster, meta: dict) -> None:
    # model_to_string keeps the pandas category mapping, so scoring maps categories the same way
    for name, booster in (("regressor", regressor), ("classifier", classifier)):
        storage.upload(f"{CHAMPION}/{name}.txt.gz", gzip.compress(booster.model_to_string().encode()),
                       "application/gzip", BUCKET)
    storage.upload(f"{CHAMPION}/meta.json", json.dumps(meta, default=str).encode(), "application/json", BUCKET)


def load_champion() -> tuple[lgb.Booster, lgb.Booster, dict] | None:
    """Downloads only the tiny meta.json each run; the ~1 MB model files come from a local cache
    (kept between GitHub runs by actions/cache) unless a new version was promoted.
    Saves ~1.4 GB/month of the 5 GB Supabase egress allowance."""
    meta_bytes = storage.download(f"{CHAMPION}/meta.json", BUCKET)
    if meta_bytes is None:
        return None
    meta = json.loads(meta_bytes)
    cache = Path(os.getenv("MODEL_CACHE_DIR", Path.home() / ".cache" / "db_delay_model"))
    boosters = []
    for name in ("regressor", "classifier"):
        path = cache / f"{meta['model_version']}_{name}.txt.gz"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(storage.download(f"{CHAMPION}/{name}.txt.gz", BUCKET))
        boosters.append(lgb.Booster(model_str=gzip.decompress(path.read_bytes()).decode()))
    return boosters[0], boosters[1], meta
