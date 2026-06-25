from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from quant_project_daily.config import ProjectPaths
from quant_project_daily.features_long_only_phase1 import (
    PHASE1_FEATURE_SET,
    _build_long_only_h5_phase1_features_polars,
    _build_long_only_h5_features_polars,
    load_long_only_h5_feature_config,
    load_long_only_h5_phase1_feature_config,
    run_long_only_h5_feature_set,
    run_long_only_h5_feature_set_wfa,
    run_long_only_h5_phase1_features,
    run_long_only_h5_phase1_wfa,
)


PHASE1_ONLY_COLUMNS = [
    "mom_20d_vol_adj",
    "mom_60d_vol_adj",
    "trend_pos_ret_frac_20d",
    "pullback_5d_vs_60d",
    "vol_ratio_5d_20d",
    "vol_ratio_20d_60d",
    "atr14_to_vol20",
    "dollar_volume_ratio_20d_60d",
]

NO_MOMENTUM_TREND = "long_only_h5_phase1_no_momentum_trend"
VOL_LIQ_ONLY = "long_only_h5_phase1_vol_liq_only"


def _labeled_frame(rows: int = 100) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=rows)
    frames = []
    for ticker, offset in [("A", 0), ("B", 100)]:
        close = pd.Series([20.0 + offset + i * 0.5 for i in range(rows)])
        open_ = close - 0.1
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
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _paths(tmp_path: Path, labeled_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "raw_txt",
        raw_manifest=tmp_path / "raw_manifest",
        validated=tmp_path / "validated",
        normalized=tmp_path / "normalized",
        causal=tmp_path / "causal",
        research_ohlcv_daily=tmp_path / "research_ohlcv_daily",
        labeled_target_h5=labeled_path,
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
        feature_matrix_long_only_h5_phase1=tmp_path / "feature_matrices" / PHASE1_FEATURE_SET,
        oos_predictions_long_only_h5_phase1=tmp_path / "oos_predictions" / PHASE1_FEATURE_SET,
    )


def test_phase1_features_are_trailing_only_and_ticker_local(tmp_path: Path) -> None:
    labeled_path = tmp_path / "target_h5.parquet"
    base = _labeled_frame(rows=100)
    base.to_parquet(labeled_path, index=False)
    paths = _paths(tmp_path, labeled_path)
    cfg = load_long_only_h5_phase1_feature_config()

    base_data, _, _ = _build_long_only_h5_phase1_features_polars(paths, cfg)

    changed = base.copy()
    changed.loc[(changed["ticker"] == "A") & (changed["date"] >= pd.Timestamp("2020-04-15")), ["close", "high", "low", "volume", "dollar_volume"]] = [
        9999.0,
        10000.0,
        9998.0,
        9_999_999,
        99_999_999.0,
    ]
    changed_path = tmp_path / "target_h5_changed.parquet"
    changed.to_parquet(changed_path, index=False)
    changed_paths = _paths(tmp_path, changed_path)
    changed_data, _, _ = _build_long_only_h5_phase1_features_polars(changed_paths, cfg)

    base_pd = base_data.to_pandas().sort_values(["ticker", "date"]).reset_index(drop=True)
    changed_pd = changed_data.to_pandas().sort_values(["ticker", "date"]).reset_index(drop=True)
    early = (base_pd["ticker"] == "A") & (pd.to_datetime(base_pd["date"]) < pd.Timestamp("2020-04-15"))
    for col in PHASE1_ONLY_COLUMNS:
        pd.testing.assert_series_equal(
            base_pd.loc[early, col].reset_index(drop=True),
            changed_pd.loc[early, col].reset_index(drop=True),
            check_names=False,
        )

    b_rows = base_pd["ticker"] == "B"
    for col in PHASE1_ONLY_COLUMNS:
        pd.testing.assert_series_equal(
            base_pd.loc[b_rows, col].reset_index(drop=True),
            changed_pd.loc[b_rows, col].reset_index(drop=True),
            check_names=False,
        )


def test_phase1_feature_run_writes_experimental_path_only(tmp_path: Path) -> None:
    labeled_path = tmp_path / "target_h5.parquet"
    _labeled_frame(rows=100).to_parquet(labeled_path, index=False)
    paths = _paths(tmp_path, labeled_path)

    with patch("quant_project_daily.features_long_only_phase1.reset_parquet_output_dir") as mock_reset:
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        summary = run_long_only_h5_phase1_features(paths=paths)

    phase1_dir = paths.feature_matrix_long_only_h5_phase1
    assert phase1_dir is not None
    assert summary["feature_set"] == PHASE1_FEATURE_SET
    assert (phase1_dir / "long_only_h5_phase1.parquet").exists()
    assert (phase1_dir / "feature_cols.json").exists()
    assert (paths.feature_reports / "long_only_h5_phase1_summary.json").exists()
    assert not paths.feature_matrix_baseline_h5.exists()
    assert not paths.oos_predictions_baseline_h5.exists()


def test_phase1_wfa_wrapper_writes_experimental_predictions_only(tmp_path: Path) -> None:
    labeled_path = tmp_path / "unused_target_h5.parquet"
    pd.DataFrame().to_parquet(labeled_path, index=False)
    paths = _paths(tmp_path, labeled_path)
    phase1_dir = paths.feature_matrix_long_only_h5_phase1
    oos_dir = paths.oos_predictions_long_only_h5_phase1
    assert phase1_dir is not None
    assert oos_dir is not None
    phase1_dir.mkdir(parents=True)
    paths.wfa_reports.mkdir(parents=True)

    for name, values in {
        "feature_cols": ["f1", "f2"],
        "target_cols": ["target_class_5d"],
        "metadata_cols": ["date", "ticker", "raw_ticker"],
        "excluded_cols": ["fwd_ret_5d"],
    }.items():
        (phase1_dir / f"{name}.json").write_text(json.dumps(values), encoding="utf-8")

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
                }
            )
    pd.DataFrame(rows).to_parquet(phase1_dir / "long_only_h5_phase1.parquet", index=False)
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

    with patch("quant_project_daily.features_long_only_phase1.reset_parquet_output_dir") as mock_reset, patch(
        "quant_project_daily.features_long_only_phase1.load_model_config",
        return_value={"model_type": "ridge", "ridge_alpha": 1.0, "target_column": "target_class_5d"},
    ):
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        summary = run_long_only_h5_phase1_wfa(paths=paths)

    assert summary["feature_set"] == PHASE1_FEATURE_SET
    assert summary["folds_completed"] == 1
    assert (oos_dir / "fold_001.parquet").exists()
    assert (paths.wfa_reports / "long_only_h5_phase1_oos_summary.json").exists()
    assert not paths.oos_predictions_baseline_h5.exists()


def test_ablation_variant_configs_include_and_exclude_expected_features() -> None:
    no_mom = load_long_only_h5_feature_config(NO_MOMENTUM_TREND)
    vol_liq = load_long_only_h5_feature_config(VOL_LIQ_ONLY)

    for cfg in [no_mom, vol_liq]:
        assert "vol_ratio_5d_20d" in cfg["feature_columns"]
        assert "vol_ratio_20d_60d" in cfg["feature_columns"]
        assert "atr14_to_vol20" in cfg["feature_columns"]
        assert "dollar_volume_ratio_20d_60d" in cfg["feature_columns"]
        assert "target_class_5d" not in cfg["feature_columns"]
        assert "fwd_ret_5d" not in cfg["feature_columns"]
        assert "next_open" not in cfg["feature_columns"]

    assert "pullback_5d_vs_60d" in no_mom["feature_columns"]
    for col in ["mom_20d_vol_adj", "mom_60d_vol_adj", "trend_pos_ret_frac_20d"]:
        assert col not in no_mom["feature_columns"]

    for col in ["mom_20d_vol_adj", "mom_60d_vol_adj", "trend_pos_ret_frac_20d", "pullback_5d_vs_60d"]:
        assert col not in vol_liq["feature_columns"]


def test_ablation_variant_feature_run_writes_variant_path_only(tmp_path: Path) -> None:
    labeled_path = tmp_path / "target_h5.parquet"
    _labeled_frame(rows=100).to_parquet(labeled_path, index=False)
    paths = _paths(tmp_path, labeled_path)

    with patch("quant_project_daily.features_long_only_phase1.reset_parquet_output_dir") as mock_reset:
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        summary = run_long_only_h5_feature_set(NO_MOMENTUM_TREND, paths=paths)

    variant_dir = tmp_path / "data" / "feature_matrices" / NO_MOMENTUM_TREND
    assert summary["feature_set"] == NO_MOMENTUM_TREND
    assert (variant_dir / f"{NO_MOMENTUM_TREND}.parquet").exists()
    assert (variant_dir / "feature_cols.json").exists()
    assert (paths.feature_reports / f"{NO_MOMENTUM_TREND}_summary.json").exists()
    assert not paths.feature_matrix_baseline_h5.exists()
    assert not paths.oos_predictions_baseline_h5.exists()


def test_ablation_variant_wfa_writes_variant_predictions_only(tmp_path: Path) -> None:
    labeled_path = tmp_path / "unused_target_h5.parquet"
    pd.DataFrame().to_parquet(labeled_path, index=False)
    paths = _paths(tmp_path, labeled_path)
    variant_dir = tmp_path / "data" / "feature_matrices" / VOL_LIQ_ONLY
    oos_dir = tmp_path / "data" / "oos_predictions" / VOL_LIQ_ONLY
    variant_dir.mkdir(parents=True)
    paths.wfa_reports.mkdir(parents=True)

    for name, values in {
        "feature_cols": ["f1", "f2"],
        "target_cols": ["target_class_5d"],
        "metadata_cols": ["date", "ticker", "raw_ticker"],
        "excluded_cols": ["fwd_ret_5d"],
    }.items():
        (variant_dir / f"{name}.json").write_text(json.dumps(values), encoding="utf-8")

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
                }
            )
    pd.DataFrame(rows).to_parquet(variant_dir / f"{VOL_LIQ_ONLY}.parquet", index=False)
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

    with patch("quant_project_daily.features_long_only_phase1.reset_parquet_output_dir") as mock_reset, patch(
        "quant_project_daily.features_long_only_phase1.load_model_config",
        return_value={"model_type": "ridge", "ridge_alpha": 1.0, "target_column": "target_class_5d"},
    ):
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        summary = run_long_only_h5_feature_set_wfa(VOL_LIQ_ONLY, paths=paths)

    assert summary["feature_set"] == VOL_LIQ_ONLY
    assert summary["folds_completed"] == 1
    assert (oos_dir / "fold_001.parquet").exists()
    assert (paths.wfa_reports / f"{VOL_LIQ_ONLY}_oos_summary.json").exists()
    assert not paths.oos_predictions_baseline_h5.exists()
