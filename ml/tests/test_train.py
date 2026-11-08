import numpy as np
import pandas as pd

from ml.train import decide, evaluate, time_split


def _synthetic(n=4000, seed=0) -> pd.DataFrame:
    """Delay depends on current delay and station: a learnable signal the baseline only half sees."""
    rng = np.random.default_rng(seed)
    cur = rng.choice([0, 0, 0, 2, 5, 10, 20], n)
    eva = rng.choice([1, 2, 3], n)
    return pd.DataFrame({
        "eva": eva, "train_category": rng.choice(["ICE", "RE", "S"], n), "line": None,
        "minutes_to_departure": rng.integers(25, 66, n), "current_delay_min": cur,
        "has_realtime": True, "station_avg_delay_30m": rng.normal(3, 1, n),
        "station_cancellations_60m": 0, "upstream_delay_min": cur, "hour_of_day": rng.integers(0, 24, n),
        "iso_weekday": rng.integers(1, 8, n), "temperature_c": 10.0, "precipitation_mm": 0.0,
        "snowfall_cm": 0.0, "wind_gust_kmh": 20.0,
        "planned_dep": pd.date_range("2026-11-01", periods=n, freq="5min", tz="UTC"),
        "actual_delay_min": (cur + eva + rng.normal(0, 1, n)).round().astype(int),
    })


def test_time_split_is_chronological():
    train, test = time_split(_synthetic())
    assert train["planned_dep"].max() < test["planned_dep"].min()
    assert 0.15 < len(test) / (len(train) + len(test)) < 0.35  # short history: last quarter


def test_model_beats_baseline_on_learnable_signal():
    m = evaluate(*time_split(_synthetic()))
    assert m["mae_model"] < m["mae_baseline"]
    assert m["auc_model"] > 0.9
    assert decide(m)[0] is True


def test_decide_rejects_worse_or_tiny():
    good = {"test_rows": 1000, "mae_model": 2.0, "mae_baseline": 3.0, "mae_persistence": 2.5}
    assert decide(good) == (True, "beats baseline")
    assert decide({**good, "mae_model": 3.0})[0] is False
    assert decide({**good, "test_rows": 10})[0] is False
