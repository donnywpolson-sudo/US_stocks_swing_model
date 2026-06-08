from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ProjectPaths:
    repo_root: Path
    raw_txt: Path
    raw_manifest: Path
    validated: Path
    normalized: Path
    causal: Path
    research_ohlcv_daily: Path
    labeled_target_h20: Path
    feature_matrix_baseline_h20: Path
    validation_reports: Path
    label_reports: Path
    feature_reports: Path
    wfa_reports: Path


def load_project_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or REPO_ROOT / "configs" / "project.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_paths(config: dict[str, Any] | None = None) -> ProjectPaths:
    cfg = config or load_project_config()
    paths = cfg["paths"]

    def rel(key: str) -> Path:
        return REPO_ROOT / paths[key]

    return ProjectPaths(
        repo_root=REPO_ROOT,
        raw_txt=rel("raw_txt"),
        raw_manifest=rel("raw_manifest"),
        validated=rel("validated"),
        normalized=rel("normalized"),
        causal=rel("causal"),
        research_ohlcv_daily=rel("research_ohlcv_daily"),
        labeled_target_h20=rel("labeled_target_h20"),
        feature_matrix_baseline_h20=rel("feature_matrix_baseline_h20"),
        validation_reports=rel("validation_reports"),
        label_reports=rel("label_reports"),
        feature_reports=rel("feature_reports"),
        wfa_reports=rel("wfa_reports"),
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def reset_parquet_output_dir(path: Path) -> None:
    resolved = path.resolve()
    root = REPO_ROOT.resolve()
    if root not in resolved.parents or resolved.name == "raw_txt":
        raise ValueError(f"unsafe generated output path: {path}")
    path.mkdir(parents=True, exist_ok=True)
    for old in path.rglob("*.parquet"):
        old.unlink()
