from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from scripts.project_config import ProjectPaths
from scripts.phase8_model_selection.daily_underlying_signals import CANDIDATE_COLUMNS, build_daily_underlying_signals, run_daily_underlying_signals


def _paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "raw_txt",
        raw_manifest=tmp_path / "raw_manifest",
        validated=tmp_path / "validated",
        normalized=tmp_path / "normalized",
        causal=tmp_path / "causal",
        research_ohlcv_daily=tmp_path / "research_ohlcv_daily",
        labeled_target_h5=tmp_path / "targets",
        feature_matrix_baseline_h5=tmp_path / "feature_matrix_baseline_h5",
        feature_matrix_expanded_h5=tmp_path / "feature_matrix_expanded_h5",
        frozen_features_expanded_h5_v1=tmp_path / "frozen",
        oos_predictions_baseline_h5=tmp_path / "oos",
        validation_reports=tmp_path / "validation_reports",
        label_reports=tmp_path / "label_reports",
        feature_reports=tmp_path / "feature_reports",
        wfa_reports=tmp_path / "wfa_reports",
        metrics_reports=tmp_path / "metrics_reports",
        gates_reports=tmp_path / "gates_reports",
        feature_matrix_baseline_h5_scoring=tmp_path / "feature_matrix_baseline_h5_scoring",
        signals_reports=tmp_path / "signals",
    )


def _train_frame(include_score_date_row: bool = False) -> pd.DataFrame:
    rows = []
    for d in pd.bdate_range("2020-01-01", periods=6):
        for i in range(20):
            rows.append(
                {
                    "date": d,
                    "ticker": f"T{i:02d}",
                    "raw_ticker": f"T{i:02d}.US",
                    "f1": float(i),
                    "f2": float(d.day),
                    "target_class_5d": [-1, 0, 1][i % 3],
                }
            )
    if include_score_date_row:
        rows.append(
            {
                "date": pd.Timestamp("2020-01-15"),
                "ticker": "T99",
                "raw_ticker": "T99.US",
                "f1": 999_999.0,
                "f2": 999_999.0,
                "target_class_5d": 999_999.0,
            }
        )
    return pd.DataFrame(rows)


def _score_frame() -> pd.DataFrame:
    rows = []
    for i in range(20):
        rows.append(
            {
                "date": pd.Timestamp("2020-01-15"),
                "ticker": f"T{i:02d}",
                "raw_ticker": f"T{i:02d}.US",
                "model_eligible": True,
                "close": 20.0,
                "volume": 1_000_000 + i,
                "dollar_volume": 30_000_000.0 + i,
                "median_dollar_volume_60": 60_000_000.0 if i >= 10 else 30_000_000.0,
                "zero_volume_count_60": 0.0,
                "history_bars": 300,
                "f1": float(i),
                "f2": 15.0,
            }
        )
    return pd.DataFrame(rows)


def _model_cfg() -> dict[str, object]:
    return {
        "model_name": "baseline_ridge_h5",
        "model_type": "ridge_regression",
        "target_column": "target_class_5d",
        "ridge_alpha": 1.0,
    }


def test_daily_underlying_signal_candidates_are_review_only_schema() -> None:
    result = build_daily_underlying_signals(
        _train_frame(),
        _score_frame(),
        feature_cols=["f1", "f2"],
        target_cols=["target_class_5d"],
        metadata_cols=["date", "ticker", "raw_ticker"],
        excluded_cols=[],
        model_cfg=_model_cfg(),
    )

    assert list(result.candidates.columns) == CANDIDATE_COLUMNS
    assert len(result.candidates) == 4
    assert sorted(result.candidates["signal_decile"].unique().tolist()) == [1, 10]
    assert result.candidates["candidate_export_type"].unique().tolist() == ["future_daily_underlying_signal_review"]
    assert not result.candidates["options_liquidity_verified"].any()
    assert "target_class_5d" not in result.candidates.columns
    assert "fwd_ret_5d" not in result.candidates.columns

    expected_25m = (
        (result.candidates["close"] >= 10)
        & (result.candidates["median_dollar_volume_60"] >= 25_000_000)
        & (result.candidates["zero_volume_count_60"] == 0)
        & (result.candidates["history_bars"] >= 252)
    )
    expected_50m = (
        (result.candidates["close"] >= 10)
        & (result.candidates["median_dollar_volume_60"] >= 50_000_000)
        & (result.candidates["zero_volume_count_60"] == 0)
        & (result.candidates["history_bars"] >= 252)
    )
    pd.testing.assert_series_equal(result.candidates["passes_option_underlying_proxy_25m"], expected_25m, check_names=False)
    pd.testing.assert_series_equal(result.candidates["passes_option_underlying_proxy_50m"], expected_50m, check_names=False)
    assert result.summary["model_persisted"] is False
    assert result.summary["model_artifact_path"] is None


def test_daily_underlying_signal_excludes_score_date_rows_from_training() -> None:
    base = build_daily_underlying_signals(
        _train_frame(),
        _score_frame(),
        feature_cols=["f1", "f2"],
        target_cols=["target_class_5d"],
        metadata_cols=["date", "ticker", "raw_ticker"],
        excluded_cols=[],
        model_cfg=_model_cfg(),
    ).candidates
    changed = build_daily_underlying_signals(
        _train_frame(include_score_date_row=True),
        _score_frame(),
        feature_cols=["f1", "f2"],
        target_cols=["target_class_5d"],
        metadata_cols=["date", "ticker", "raw_ticker"],
        excluded_cols=[],
        model_cfg=_model_cfg(),
    ).candidates

    pd.testing.assert_series_equal(base["pred_score_5d"], changed["pred_score_5d"], check_names=False)


def test_daily_underlying_signal_rejects_forbidden_feature_columns() -> None:
    with pytest.raises(ValueError, match="feature_cols contain leakage columns"):
        build_daily_underlying_signals(
            _train_frame(),
            _score_frame(),
            feature_cols=["f1", "target_class_5d"],
            target_cols=["target_class_5d"],
            metadata_cols=["date", "ticker", "raw_ticker"],
            excluded_cols=[],
            model_cfg=_model_cfg(),
        )


def test_run_daily_underlying_signals_writes_csv_and_summary_without_model_artifact(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.feature_matrix_baseline_h5.mkdir(parents=True)
    paths.feature_matrix_baseline_h5_scoring.mkdir(parents=True)

    _train_frame().to_parquet(paths.feature_matrix_baseline_h5 / "baseline_h5.parquet", index=False)
    _score_frame().to_parquet(paths.feature_matrix_baseline_h5_scoring / "baseline_h5_scoring.parquet", index=False)
    (paths.feature_matrix_baseline_h5 / "feature_cols.json").write_text('["f1", "f2"]', encoding="utf-8")
    (paths.feature_matrix_baseline_h5 / "target_cols.json").write_text('["target_class_5d"]', encoding="utf-8")
    (paths.feature_matrix_baseline_h5 / "metadata_cols.json").write_text('["date", "ticker", "raw_ticker"]', encoding="utf-8")
    (paths.feature_matrix_baseline_h5 / "excluded_cols.json").write_text("[]", encoding="utf-8")

    with patch("scripts.phase8_model_selection.daily_underlying_signals.load_model_config", return_value=_model_cfg()):
        summary = run_daily_underlying_signals(paths=paths, rebuild_scoring=False)

    candidate_path = paths.signals_reports / "baseline_h5_daily_underlying_candidates.csv"
    summary_path = paths.signals_reports / "baseline_h5_daily_underlying_signal_summary.json"
    assert candidate_path.exists()
    assert summary_path.exists()
    assert summary["model_persisted"] is False
    assert summary["candidate_rows"] == 4
    assert summary["model_artifact_path"] is None
