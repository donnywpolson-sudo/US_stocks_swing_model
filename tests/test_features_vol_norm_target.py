from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.project_config import ProjectPaths
from scripts.phase9_research.features_vol_norm_target import (
    VOL_NORM60_FEATURE_SET,
    _build_vol_norm60_target_features_polars,
    load_vol_norm60_target_feature_config,
    run_vol_norm60_target_features,
    run_vol_norm60_target_wfa,
    vol_norm60_feature_matrix_path,
    vol_norm60_oos_prediction_path,
)


def _experimental_target_frame(rows: int = 100) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=rows)
    frames = []
    for ticker, offset in [("A", 0), ("B", 100)]:
        close = pd.Series([20.0 + offset + i * 0.1 + np.sin(i / 5.0) * 0.2 for i in range(rows)])
        open_ = close - 0.05
        volume = pd.Series([1000 + offset + i for i in range(rows)])
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "open": open_,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": volume,
                    "dollar_volume": close * volume,
                    "model_eligible": True,
                    "next_open": open_.shift(-1),
                    "exit_close_5d": close.shift(-5),
                    "exit_date_5d": dates.to_series().shift(-5).to_numpy(),
                    "fwd_ret_5d": close.shift(-5) / open_.shift(-1) - 1,
                    "has_split_like_gap_in_target_window_5d": False,
                    "label_valid_5d": True,
                    "target_class_5d": 0,
                    "target_long_top20_5d": False,
                    "target_short_bottom20_5d": False,
                    "fwd_ret_5d_vol_norm60": 0.1,
                    "label_valid_5d_vol_norm60": True,
                    "target_class_5d_vol_norm60": 0,
                    "target_long_top20_5d_vol_norm60": False,
                    "target_short_bottom20_5d_vol_norm60": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _paths(tmp_path: Path, target_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "raw_txt",
        raw_manifest=tmp_path / "raw_manifest",
        validated=tmp_path / "validated",
        normalized=tmp_path / "normalized",
        causal=tmp_path / "causal",
        research_ohlcv_daily=tmp_path / "research_ohlcv_daily",
        labeled_target_h5=tmp_path / "official_target_h5",
        feature_matrix_baseline_h5=tmp_path / "official_baseline_h5",
        feature_matrix_expanded_h5=tmp_path / "expanded_h5",
        frozen_features_expanded_h5_v1=tmp_path / "frozen",
        oos_predictions_baseline_h5=tmp_path / "official_oos_baseline_h5",
        validation_reports=tmp_path / "reports" / "validation",
        label_reports=tmp_path / "reports" / "labels",
        feature_reports=tmp_path / "reports" / "features",
        wfa_reports=tmp_path / "reports" / "wfa",
        metrics_reports=tmp_path / "reports" / "metrics",
        gates_reports=tmp_path / "reports" / "gates",
    )


def test_vol_norm60_target_feature_config_is_baseline_features_only() -> None:
    cfg = load_vol_norm60_target_feature_config()

    assert cfg["feature_set"] == VOL_NORM60_FEATURE_SET
    assert len(cfg["feature_columns"]) == 55
    for col in [
        "target_class_5d",
        "fwd_ret_5d",
        "target_class_5d_vol_norm60",
        "fwd_ret_5d_vol_norm60",
        "label_valid_5d_vol_norm60",
        "next_open",
        "exit_close_5d",
    ]:
        assert col not in cfg["feature_columns"]


def test_vol_norm60_target_features_are_trailing_only(tmp_path: Path) -> None:
    target_path = tmp_path / "data" / "labeled" / "target_h5_vol_norm60_experimental"
    target_path.mkdir(parents=True)
    base = _experimental_target_frame(rows=100)
    base.to_parquet(target_path / "targets.parquet", index=False)
    paths = _paths(tmp_path, target_path)
    cfg = load_vol_norm60_target_feature_config()

    base_data, _, _ = _build_vol_norm60_target_features_polars(paths, cfg)

    changed = base.copy()
    cutoff = pd.Timestamp("2020-04-15")
    changed.loc[(changed["ticker"] == "A") & (changed["date"] >= cutoff), ["close", "high", "low", "volume", "dollar_volume"]] = [
        9999.0,
        10000.0,
        9998.0,
        9_999_999,
        99_999_999.0,
    ]
    changed.to_parquet(target_path / "targets.parquet", index=False)
    changed_data, _, _ = _build_vol_norm60_target_features_polars(paths, cfg)

    base_pd = base_data.to_pandas().sort_values(["ticker", "date"]).reset_index(drop=True)
    changed_pd = changed_data.to_pandas().sort_values(["ticker", "date"]).reset_index(drop=True)
    early = (base_pd["ticker"] == "A") & (pd.to_datetime(base_pd["date"]) < cutoff)
    for col in cfg["feature_columns"]:
        pd.testing.assert_series_equal(
            base_pd.loc[early, col].reset_index(drop=True),
            changed_pd.loc[early, col].reset_index(drop=True),
            check_names=False,
        )


def test_vol_norm60_target_feature_run_writes_experimental_path_only(tmp_path: Path) -> None:
    target_path = tmp_path / "data" / "labeled" / "target_h5_vol_norm60_experimental"
    target_path.mkdir(parents=True)
    _experimental_target_frame(rows=100).to_parquet(target_path / "targets.parquet", index=False)
    paths = _paths(tmp_path, target_path)

    with patch("scripts.phase9_research.features_vol_norm_target.reset_parquet_output_dir") as mock_reset:
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        summary = run_vol_norm60_target_features(paths=paths)

    out_path = vol_norm60_feature_matrix_path(paths)
    assert summary["feature_set"] == VOL_NORM60_FEATURE_SET
    assert summary["target_column"] == "target_class_5d_vol_norm60"
    assert summary["feature_count"] == 55
    assert (out_path / "long_only_h5_vol_norm60_target.parquet").exists()
    assert (out_path / "feature_cols.json").exists()
    assert (paths.feature_reports / "long_only_h5_vol_norm60_target_summary.json").exists()
    assert not paths.feature_matrix_baseline_h5.exists()
    assert not paths.oos_predictions_baseline_h5.exists()


def test_vol_norm60_target_wfa_writes_experimental_predictions_only(tmp_path: Path) -> None:
    target_path = tmp_path / "data" / "labeled" / "target_h5_vol_norm60_experimental"
    paths = _paths(tmp_path, target_path)
    feature_dir = vol_norm60_feature_matrix_path(paths)
    oos_dir = vol_norm60_oos_prediction_path(paths)
    feature_dir.mkdir(parents=True)
    paths.wfa_reports.mkdir(parents=True)

    for name, values in {
        "feature_cols": ["f1", "f2"],
        "target_cols": ["target_class_5d", "target_class_5d_vol_norm60"],
        "metadata_cols": ["date", "ticker", "raw_ticker"],
        "excluded_cols": ["fwd_ret_5d", "fwd_ret_5d_vol_norm60"],
    }.items():
        (feature_dir / f"{name}.json").write_text(json.dumps(values), encoding="utf-8")

    rows = []
    dates = pd.bdate_range("2020-01-01", periods=8)
    for d in dates:
        for i, ticker in enumerate(["A", "B", "C"]):
            rows.append(
                {
                    "date": d,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "f1": float(i),
                    "f2": float(d.day),
                    "target_class_5d": [-1, 0, 1][i],
                    "fwd_ret_5d": [-0.1, 0.0, 0.1][i],
                    "target_class_5d_vol_norm60": [-1, 0, 1][i],
                    "fwd_ret_5d_vol_norm60": [-1.0, 0.0, 1.0][i],
                }
            )
    pd.DataFrame(rows).to_parquet(feature_dir / "long_only_h5_vol_norm60_target.parquet", index=False)
    pd.DataFrame(
        {
            "fold_id": [1],
            "train_start_date": ["2020-01-01"],
            "train_end_date": ["2020-01-06"],
            "test_start_date": ["2020-01-07"],
            "test_end_date": ["2020-01-10"],
            "train_row_count": [12],
            "test_row_count": [12],
        }
    ).to_csv(paths.wfa_reports / "baseline_h5_split_plan.csv", index=False)

    with patch("scripts.phase9_research.features_vol_norm_target.reset_parquet_output_dir") as mock_reset, patch(
        "scripts.phase9_research.features_vol_norm_target.load_model_config",
        return_value={"model_type": "ridge", "ridge_alpha": 1.0, "target_column": "target_class_5d_vol_norm60"},
    ):
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        summary = run_vol_norm60_target_wfa(paths=paths)

    assert summary["feature_set"] == VOL_NORM60_FEATURE_SET
    assert summary["target_column"] == "target_class_5d_vol_norm60"
    assert summary["folds_completed"] == 1
    assert (oos_dir / "fold_001.parquet").exists()
    assert (paths.wfa_reports / "long_only_h5_vol_norm60_target_oos_summary.json").exists()
    assert not paths.oos_predictions_baseline_h5.exists()
