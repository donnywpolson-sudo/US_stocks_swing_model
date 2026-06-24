from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quant_project_daily.metrics import build_metrics, run_metrics
from quant_project_daily.config import ProjectPaths


def _make_paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path,
        raw_manifest=tmp_path,
        validated=tmp_path,
        normalized=tmp_path,
        causal=tmp_path,
        research_ohlcv_daily=tmp_path,
        labeled_target_h5=tmp_path,
        feature_matrix_baseline_h5=tmp_path,
        feature_matrix_expanded_h5=tmp_path,
        frozen_features_expanded_h5_v1=tmp_path,
        oos_predictions_baseline_h5=tmp_path / "oos_preds",
        validation_reports=tmp_path,
        label_reports=tmp_path,
        feature_reports=tmp_path,
        wfa_reports=tmp_path,
        metrics_reports=tmp_path / "metrics_reports",
        gates_reports=tmp_path / "gates_reports",
    )


def _min_cfg() -> dict:
    return {
        "round_trip_cost_bps": 25,
        "decile_buckets": 10,
        "quintile_buckets": 5,
        "score_outlier_abs_threshold": 5.0,
    }


def _make_pred_rows(n_rows: int, n_dates: int = 2, n_folds: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows_per_date = n_rows // n_dates
    rows: list[dict] = []
    for d in range(n_dates):
        for i in range(rows_per_date):
            fold_id = i % n_folds
            rows.append(
                {
                    "fold_id": fold_id,
                    "date": f"2024-01-{d + 1:02d}",
                    "ticker": f"TICK{i}",
                    "raw_ticker": f"TICK{i}",
                    "target_class_5d": 1 if i % 2 == 0 else 0,
                    "fwd_ret_5d": float(rng.uniform(-0.05, 0.08)),
                    "pred_score_5d": float(rng.uniform(-3.0, 3.0)),
                    "pred_rank_pct_by_date": float(rng.uniform(0, 1)),
                    "pred_long_rank_5d": i + 1,
                    "pred_short_rank_5d": i + 1,
                }
            )
    return pd.DataFrame(rows)


class TestBuildMetrics:
    def test_empty_df_returns_blocker(self) -> None:
        cfg = _min_cfg()
        empty = pd.DataFrame()
        summary, _ = build_metrics(empty, cfg)
        blockers = summary["blockers"]
        assert "missing_oos_predictions" in blockers

    def test_null_prediction_rows_triggers_warning(self) -> None:
        cfg = _min_cfg()
        df = _make_pred_rows(20, n_dates=2, n_folds=2)
        df.loc[0, "pred_score_5d"] = np.nan
        df.loc[1, "fwd_ret_5d"] = np.nan
        summary, _ = build_metrics(df, cfg)
        warnings = summary["warnings"]
        assert "missing_or_null_prediction_rows" in warnings
        assert summary["missing_or_null_prediction_rows"] > 0

    def test_too_few_names_triggers_ranking_warnings(self) -> None:
        """When bucket count exceeds names per date, ranking warnings appear."""
        cfg = _min_cfg()
        df = _make_pred_rows(6, n_dates=2, n_folds=2)
        summary, _ = build_metrics(df, cfg)
        warnings = summary["warnings"]
        assert "dates_with_too_few_names_for_deciles" in warnings
        assert summary["dates_with_too_few_names_for_decile_ranking"] > 0


class TestRunMetrics:
    def test_run_metrics_integration(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        paths.oos_predictions_baseline_h5.mkdir(parents=True, exist_ok=True)
        paths.metrics_reports.mkdir(parents=True, exist_ok=True)

        df = _make_pred_rows(60, n_dates=3, n_folds=3)
        df.to_parquet(paths.oos_predictions_baseline_h5 / "preds.parquet")

        summary = run_metrics(paths=paths)

        assert (paths.metrics_reports / "baseline_h5_metrics_summary.json").exists()

        csv_files = list(paths.metrics_reports.glob("baseline_h5_*.csv"))
        assert len(csv_files) >= 1

        assert summary["total_oos_rows"] > 0