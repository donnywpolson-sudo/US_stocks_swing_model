from pathlib import Path

import pandas as pd

from quant_project_daily.config import ProjectPaths
from quant_project_daily.validation_diagnostics import run_validation_diagnostics


def _paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "data" / "raw_txt",
        raw_manifest=tmp_path / "data" / "raw_manifest" / "raw_manifest.parquet",
        validated=tmp_path / "data" / "validated",
        normalized=tmp_path / "data" / "normalized",
        causal=tmp_path / "data" / "causal",
        research_ohlcv_daily=tmp_path / "data" / "research_ohlcv_daily",
        labeled_target_h20=tmp_path / "data" / "labeled" / "target_h20",
        feature_matrix_baseline_h20=tmp_path / "data" / "feature_matrices" / "baseline_h20",
        feature_matrix_expanded_h20=tmp_path / "data" / "feature_matrices" / "expanded_h20",
        frozen_features_expanded_h20_v1=tmp_path / "data" / "frozen_features" / "expanded_h20_v1",
        oos_predictions_baseline_h20=tmp_path / "data" / "oos_predictions" / "baseline_h20",
        validation_reports=tmp_path / "reports" / "validation",
        label_reports=tmp_path / "reports" / "labels",
        feature_reports=tmp_path / "reports" / "features",
        wfa_reports=tmp_path / "reports" / "wfa",
        metrics_reports=tmp_path / "reports" / "metrics",
        gates_reports=tmp_path / "reports" / "gates",
    )


def test_validation_diagnostics_outputs_reports(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    p.raw_manifest.parent.mkdir(parents=True)
    p.validated.mkdir(parents=True)
    p.causal.mkdir(parents=True)
    p.validation_reports.mkdir(parents=True)

    pd.DataFrame(
        [
            {"source_file": "a.txt", "parse_status": "ok", "error_message": ""},
            {"source_file": "bad.txt", "parse_status": "error", "error_message": "empty"},
        ]
    ).to_parquet(p.raw_manifest, index=False)

    validated = pd.DataFrame(
        [
            {"ticker": "A", "date": "2024-01-01", "open": 10.0, "close": 10.0, "volume": 0, "year": 2024},
            {"ticker": "A", "date": "2024-01-02", "open": 20.0, "close": 21.0, "volume": 100, "year": 2024},
        ]
    )
    validated.to_parquet(p.validated / "part.parquet", index=False)

    causal = validated.copy()
    causal["tradable"] = [False, True]
    causal.to_parquet(p.causal / "part.parquet", index=False)
    pd.DataFrame([{"ticker": "A", "date": "2024-01-02", "reason": "bad_ohlc_positive"}]).to_csv(
        p.validation_reports / "raw_rejected_rows.csv", index=False
    )

    result = run_validation_diagnostics(p)

    assert result.summary["parse_error_files"] == 1
    assert result.summary["rejected_rows"] == 1
    assert result.summary["zero_volume_rows"] == 1
    assert result.summary["tradable_rows"] == 1
    assert (p.validation_reports / "parse_errors.csv").exists()
    assert (p.validation_reports / "tradable_coverage_by_ticker.csv").exists()
