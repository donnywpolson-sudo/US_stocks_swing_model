from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from quant_project_daily.config import REPO_ROOT, project_paths


def load_baseline_feature_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / "baseline_features.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_column_registry(columns: list[str], cfg: dict[str, Any]) -> dict[str, list[str]]:
    actual = set(columns)
    missing_groups: dict[str, list[str]] = {}

    missing_features = sorted(set(cfg["feature_columns"]) - actual)
    if missing_features:
        missing_groups["feature_columns"] = missing_features

    missing_targets = sorted(set(cfg["target_columns"]) - actual)
    if missing_targets:
        missing_groups["target_columns"] = missing_targets

    missing_metadata = sorted(set(cfg["metadata_columns"]) - actual)
    if missing_metadata:
        missing_groups["metadata_columns"] = missing_metadata

    if missing_groups:
        parts = [f"  {group}: {cols}" for group, cols in missing_groups.items()]
        raise ValueError(
            "configured columns missing from actual matrix columns:\n" + "\n".join(parts)
        )

    feature_cols = [c for c in cfg["feature_columns"] if c in columns]
    target_cols = [c for c in cfg["target_columns"] if c in columns]
    metadata_cols = [c for c in cfg["metadata_columns"] if c in columns]
    configured_excluded = set(cfg["excluded_columns"])
    used = set(feature_cols) | set(target_cols) | set(metadata_cols)
    excluded_cols = [c for c in columns if c in configured_excluded or c not in used]

    leakage = set(target_cols) | set(excluded_cols)
    overlap = sorted(set(feature_cols) & leakage)
    if overlap:
        raise ValueError(f"feature registry includes leakage columns: {overlap}")
    return {
        "feature_cols": feature_cols,
        "target_cols": target_cols,
        "metadata_cols": metadata_cols,
        "excluded_cols": excluded_cols,
    }


def _matrix_columns(matrix_path: Path) -> list[str]:
    parquet_files = sorted(matrix_path.rglob("*.parquet")) if matrix_path.is_dir() else [matrix_path]
    if not parquet_files:
        raise FileNotFoundError(f"missing parquet files under: {matrix_path}")
    return list(pd.read_parquet(parquet_files[0]).columns)


def write_column_registry(matrix_path: Path | None = None, cfg: dict[str, Any] | None = None) -> dict[str, object]:
    paths = project_paths()
    cfg = cfg or load_baseline_feature_config()
    matrix_path = matrix_path or paths.feature_matrix_baseline_h5
    if not matrix_path.exists():
        raise FileNotFoundError(f"missing feature matrix: {matrix_path}")
    columns = _matrix_columns(matrix_path)
    registry = build_column_registry(columns, cfg)
    matrix_path.mkdir(parents=True, exist_ok=True)
    for name, values in registry.items():
        (matrix_path / f"{name}.json").write_text(json.dumps(values, indent=2), encoding="utf-8")
    return {
        "feature_count": len(registry["feature_cols"]),
        "target_column_count": len(registry["target_cols"]),
        "metadata_column_count": len(registry["metadata_cols"]),
        "excluded_column_count": len(registry["excluded_cols"]),
    }
