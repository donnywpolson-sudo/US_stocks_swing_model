from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.validation.audit_remediation import (
    build_data_universe_limitations_markdown,
    build_negative_control_diagnostics,
    build_provenance_manifest,
    run_audit_remediation,
)
from scripts.project_config import ProjectPaths


def _paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "data" / "raw_txt",
        raw_manifest=tmp_path / "data" / "raw_manifest" / "raw_manifest.parquet",
        validated=tmp_path / "data" / "validated",
        normalized=tmp_path / "data" / "normalized",
        causal=tmp_path / "data" / "causal",
        research_ohlcv_daily=tmp_path / "data" / "research_ohlcv_daily",
        labeled_target_h5=tmp_path / "data" / "labeled" / "target_h5",
        feature_matrix_baseline_h5=tmp_path / "data" / "feature_matrices" / "baseline_h5",
        feature_matrix_expanded_h5=tmp_path / "data" / "feature_matrices" / "expanded_h5",
        frozen_features_expanded_h5_v1=tmp_path / "data" / "frozen_features" / "expanded_h5_v1",
        oos_predictions_baseline_h5=tmp_path / "data" / "oos_predictions" / "baseline_h5",
        validation_reports=tmp_path / "reports" / "validation",
        label_reports=tmp_path / "reports" / "labels",
        feature_reports=tmp_path / "reports" / "features",
        wfa_reports=tmp_path / "reports" / "wfa",
        metrics_reports=tmp_path / "reports" / "metrics",
        gates_reports=tmp_path / "reports" / "gates",
    )


def _cfg() -> dict:
    return {
        "round_trip_cost_bps": 25,
        "decile_buckets": 10,
        "quintile_buckets": 5,
        "score_outlier_abs_threshold": 5.0,
    }


def _preds(n_dates: int = 4, n_names: int = 12) -> pd.DataFrame:
    rng = np.random.default_rng(101)
    rows: list[dict] = []
    for d in range(n_dates):
        for i in range(n_names):
            rows.append(
                {
                    "fold_id": d % 2,
                    "date": f"2024-01-{d + 2:02d}",
                    "ticker": f"TICK{i:03d}",
                    "raw_ticker": f"TICK{i:03d}",
                    "target_class_5d": int(i % 2 == 0),
                    "fwd_ret_5d": float(rng.uniform(-0.04, 0.06)),
                    "pred_score_5d": float(rng.normal()),
                    "pred_rank_pct_by_date": float(i / n_names),
                    "pred_long_rank_5d": i + 1,
                    "pred_short_rank_5d": n_names - i,
                }
            )
    return pd.DataFrame(rows)


def test_negative_controls_include_random_null_and_lagged_controls() -> None:
    summary, by_control, by_fold = build_negative_control_diagnostics(_preds(), _cfg(), seeds=(3, 5), top_n=5)

    assert summary["model_name"] == "baseline_h5"
    assert set(by_control["control_name"]) == {
        "active_model",
        "random_score_seed_3",
        "random_score_seed_5",
        "null_constant_score",
        "lagged_score_by_ticker",
    }
    assert by_control["fixed_top_n_net_return"].notna().all()
    assert by_control.loc[by_control["control_name"] == "lagged_score_by_ticker", "dropped_rows"].item() == 12
    assert not by_fold.empty


def test_limitations_report_preserves_research_guardrails(tmp_path: Path) -> None:
    report = build_data_universe_limitations_markdown(_paths(tmp_path), "2026-01-01T00:00:00+00:00")

    assert "research-ready and walk-forward-ready" in report
    assert "No point-in-time security master" in report
    assert "option P&L" in report
    assert "next_open" in report
    assert "exit_close_5d" in report


def test_provenance_manifest_records_artifacts_and_guardrails(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "project.yaml").write_text("paths: {}\n", encoding="utf-8")
    paths.metrics_reports.mkdir(parents=True)
    (paths.metrics_reports / "baseline_h5_metrics_summary.json").write_text("{}", encoding="utf-8")

    manifest = build_provenance_manifest(paths, _preds(), "2026-01-01T00:00:00+00:00")

    assert manifest["manifest_name"] == "baseline_h5_gate_provenance_manifest"
    assert manifest["oos_prediction_rows_observed"] == 48
    assert any(item["path"] == "configs/project.yaml" and item["exists"] for item in manifest["config_artifacts"])
    assert any("research-ready" in guardrail for guardrail in manifest["research_guardrails"])


def test_run_audit_remediation_writes_scoped_artifacts(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.oos_predictions_baseline_h5.mkdir(parents=True)
    _preds().to_parquet(paths.oos_predictions_baseline_h5 / "preds.parquet", index=False)

    result = run_audit_remediation(paths, execution_costs=_cfg())

    artifact_paths = {Path(p) for p in result["artifacts"].values()}
    assert artifact_paths
    assert all(path.exists() for path in artifact_paths)
    assert all("reports" in path.parts for path in artifact_paths)
    assert (paths.metrics_reports / "baseline_h5_negative_controls_by_control.csv").exists()
    assert (paths.repo_root / "reports" / "audit" / "baseline_h5_data_universe_limitations.md").exists()
