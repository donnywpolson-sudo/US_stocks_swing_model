import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest

from quant_project_daily.column_registry import build_column_registry, load_baseline_feature_config
from quant_project_daily.config import ProjectPaths
from quant_project_daily.features_baseline import (
    _build_baseline_features_polars,
    build_baseline_features,
    run_baseline_features,
)


def _labeled(tickers=("A", "B"), rows=300) -> pd.DataFrame:
    frames = []
    dates = pd.bdate_range("2010-01-01", periods=rows)
    for j, ticker in enumerate(tickers):
        base = 10 + j * 1000
        close = pd.Series(range(base, base + rows), dtype=float)
        open_ = close - 0.5
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "open": open_,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000 + j * 100 + pd.Series(range(rows)),
                    "dollar_volume": close * (1000 + j * 100 + pd.Series(range(rows))),
                    "model_eligible": True,
                    "next_open": open_.shift(-1),
                    "exit_close_20d": close.shift(-20),
                    "exit_date_20d": dates.to_series().shift(-20).to_numpy(),
                    "fwd_ret_20d": close.shift(-20) / open_.shift(-1) - 1,
                    "has_split_like_gap_in_target_window_20d": False,
                    "label_valid_20d": True,
                    "target_class_20d": 0,
                    "target_long_top20_20d": False,
                    "target_short_bottom20_20d": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_baseline_features_are_ticker_local_and_returns_are_correct() -> None:
    result = build_baseline_features(_labeled(rows=80))
    out = result.data.sort_values(["ticker", "date"]).reset_index(drop=True)
    a = out[out["ticker"] == "A"].reset_index(drop=True)
    b = out[out["ticker"] == "B"].reset_index(drop=True)
    assert a.loc[1, "ret_1d"] == a.loc[1, "close"] / a.loc[0, "close"] - 1
    assert pd.isna(b.loc[0, "ret_1d"])


def test_rolling_high_low_features_are_causal() -> None:
    df = _labeled(tickers=("A",), rows=300)
    base = build_baseline_features(df).data
    changed_future = df.copy()
    changed_future.loc[changed_future.index[-1], "high"] = 1_000_000
    changed = build_baseline_features(changed_future).data
    early = base["date"].astype(str) < "2010-06-01"
    pd.testing.assert_series_equal(
        base.loc[early, "dist_to_60d_high"].reset_index(drop=True),
        changed.loc[early, "dist_to_60d_high"].reset_index(drop=True),
        check_names=False,
    )


def test_rsi_and_volume_features_do_not_use_future_rows() -> None:
    df = _labeled(tickers=("A",), rows=120)
    base = build_baseline_features(df).data
    changed_future = df.copy()
    changed_future.loc[changed_future.index[-1], ["close", "volume", "dollar_volume"]] = [9999.0, 999999, 9999999.0]
    changed = build_baseline_features(changed_future).data
    early = base["date"].astype(str) < "2010-03-01"
    pd.testing.assert_series_equal(base.loc[early, "rsi_14"].reset_index(drop=True), changed.loc[early, "rsi_14"].reset_index(drop=True), check_names=False)
    pd.testing.assert_series_equal(base.loc[early, "volume_z_20d"].reset_index(drop=True), changed.loc[early, "volume_z_20d"].reset_index(drop=True), check_names=False)


def test_output_only_label_valid_and_no_leakage_in_feature_cols() -> None:
    df = _labeled(tickers=("A",), rows=80)
    df.loc[df.index[:5], "label_valid_20d"] = False
    result = build_baseline_features(df)
    assert len(result.data) == len(df) - 5
    forbidden = {"next_open", "exit_close_20d", "fwd_ret_20d", "target_class_20d", "label_valid_20d"}
    assert not (set(result.registry["feature_cols"]) & forbidden)
    assert set(result.registry["feature_cols"]) == set(load_baseline_feature_config()["feature_columns"])


def test_missing_configured_features_raises_value_error() -> None:
    """build_column_registry must fail when configured columns are missing from actual."""
    cfg = {
        "feature_columns": ["f1", "f2", "missing_feat"],
        "target_columns": ["target_class_20d", "missing_target"],
        "metadata_columns": ["date", "ticker", "missing_meta"],
        "excluded_columns": ["fwd_ret_20d"],
    }
    actual_columns = ["f1", "f2", "date", "ticker", "target_class_20d", "fwd_ret_20d"]
    with pytest.raises(ValueError, match="configured columns missing"):
        build_column_registry(actual_columns, cfg)


# ---------------------------------------------------------------------------
# Production polars build-path tests
# ---------------------------------------------------------------------------

_REGISTRY_KEYS = ("feature_cols", "target_cols", "metadata_cols", "excluded_cols")


def _make_polars_labeled(tmp_path: Path) -> Path:
    """Write a tiny 2-ticker labeled-target parquet and return its path."""
    rows = 300
    start = pl.date(2010, 1, 1)
    dates = pl.date_range(start, start + pl.duration(days=rows - 1), eager=True)
    frames = []
    for j, ticker in enumerate(("A", "B")):
        base = 10 + j * 1000
        close = [float(base + i) for i in range(rows)]
        open_ = [c - 0.5 for c in close]
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "ticker": [ticker] * rows,
                    "raw_ticker": [f"{ticker}.US"] * rows,
                    "open": open_,
                    "high": [c + 1 for c in close],
                    "low": [c - 1 for c in close],
                    "close": close,
                    "volume": [1000 + j * 100 + i for i in range(rows)],
                    "dollar_volume": [
                        c * (1000 + j * 100 + i) for c, i in zip(close, range(rows))
                    ],
                    "model_eligible": [True] * rows,
                    "next_open": open_[1:] + [None],
                    "exit_close_20d": [None] * 20 + close[:-20],
                    "exit_date_20d": ["2010-01-01"] * rows,
                    "fwd_ret_20d": [
                        (close[i + 20] / open_[i] - 1) if i + 20 < rows else None
                        for i in range(rows)
                    ],
                    "has_split_like_gap_in_target_window_20d": [False] * rows,
                    "label_valid_20d": [True] * rows,
                    "target_class_20d": [0] * rows,
                    "target_long_top20_20d": [False] * rows,
                    "target_short_bottom20_20d": [False] * rows,
                }
            )
        )
    df = pl.concat(frames)
    pq = tmp_path / "labeled_target_h20.parquet"
    df.write_parquet(str(pq))
    return pq


def _make_test_paths(tmp_path: Path, labeled_parquet: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "raw_txt",
        raw_manifest=tmp_path / "raw_manifest",
        validated=tmp_path / "validated",
        normalized=tmp_path / "normalized",
        causal=tmp_path / "causal",
        research_ohlcv_daily=tmp_path / "research_ohlcv_daily",
        labeled_target_h20=labeled_parquet,
        feature_matrix_baseline_h20=tmp_path / "feature_matrix_baseline_h20",
        feature_matrix_expanded_h20=tmp_path / "feature_matrix_expanded_h20",
        frozen_features_expanded_h20_v1=tmp_path / "frozen",
        oos_predictions_baseline_h20=tmp_path / "oos",
        validation_reports=tmp_path / "validation_reports",
        label_reports=tmp_path / "label_reports",
        feature_reports=tmp_path / "feature_reports",
        wfa_reports=tmp_path / "wfa_reports",
        metrics_reports=tmp_path / "metrics_reports",
        gates_reports=tmp_path / "gates_reports",
    )


def test_polars_production_feature_build(tmp_path: Path) -> None:
    """Exercise the production _build_baseline_features_polars() path.

    Verifies:
      - output parquet written
      - registry JSON files written
      - configured feature columns present
      - target/leakage columns absent from feature_cols
      - summary has nonzero output_rows
    """
    cfg = load_baseline_feature_config()
    pq = _make_polars_labeled(tmp_path)
    paths = _make_test_paths(tmp_path, pq)

    # --- 1. Direct polars build path --------------------------------------
    data, summary, registry = _build_baseline_features_polars(paths, cfg)

    assert data.height > 0, "polars build produced zero rows"
    assert summary["output_rows"] > 0, "summary output_rows is zero"
    assert summary["feature_count"] > 0, "summary feature_count is zero"

    # every configured feature column present in output
    for col in cfg["feature_columns"]:
        assert col in data.columns, f"missing feature column: {col}"

    # target / leakage columns must not appear in feature_cols
    feature_set = set(registry["feature_cols"])
    leakage = set(cfg["target_columns"]) | set(cfg["excluded_columns"])
    overlap = feature_set & leakage
    assert not overlap, f"leakage in feature_cols: {overlap}"

    # registry structure
    for key in _REGISTRY_KEYS:
        assert key in registry, f"registry missing key: {key}"

    # --- 2. Full run_baseline_features I/O path ---------------------------
    with patch(
        "quant_project_daily.features_baseline.reset_parquet_output_dir"
    ) as mock_reset:
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        io_summary = run_baseline_features(paths=paths)

    assert io_summary["output_rows"] > 0, "run output_rows is zero"

    # output parquet written
    pq_out = paths.feature_matrix_baseline_h20 / "baseline_h20.parquet"
    assert pq_out.exists(), "output parquet not written"

    # registry JSON files written
    for key in _REGISTRY_KEYS:
        json_path = paths.feature_matrix_baseline_h20 / f"{key}.json"
        assert json_path.exists(), f"registry JSON not written: {key}.json"
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(loaded, list) and len(loaded) > 0

    # summary JSON written
    summary_path = paths.feature_reports / "baseline_h20_summary.json"
    assert summary_path.exists(), "summary JSON not written"
    summary_loaded = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_loaded["output_rows"] > 0
