from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from quant_project_daily.config import REPO_ROOT, ProjectPaths, project_paths


def load_gate_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / "gates.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)["baseline_h5"]


def load_metrics(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, ["metrics_file_missing"]
    return json.loads(path.read_text(encoding="utf-8")), []


def evaluate_baseline_gate(metrics: dict[str, Any] | None, thresholds: dict[str, Any], pre_failures: list[str] | None = None) -> dict[str, Any]:
    failures = list(pre_failures or [])
    warnings: list[str] = []
    metrics = metrics or {}

    metric_blockers = metrics.get("blockers", [])
    if metric_blockers:
        failures.append("metrics_blockers_present")

    checks = {
        "total_oos_rows": (metrics.get("total_oos_rows"), ">=", thresholds["min_total_oos_rows"]),
        "fold_count": (metrics.get("fold_count"), ">=", thresholds["min_fold_count"]),
        "mean_daily_rank_ic": (metrics.get("mean_daily_rank_ic"), ">", thresholds["min_mean_daily_rank_ic"]),
        "rank_ic_t_stat": (metrics.get("rank_ic_t_stat"), ">=", thresholds["min_rank_ic_t_stat"]),
        "long_short_net_return": (metrics.get("long_short_net_return"), ">", thresholds["min_long_short_net_return"]),
        "top_decile_net_return": (metrics.get("top_decile_net_return"), ">", thresholds["min_top_decile_net_return"]),
    }
    for name, (value, op, threshold) in checks.items():
        if value is None:
            failures.append(f"{name}_missing")
        elif op == ">=" and not (value >= threshold):
            failures.append(f"{name}_below_threshold")
        elif op == ">" and not (value > threshold):
            failures.append(f"{name}_failed_positive_threshold")

    if metrics.get("bottom_decile_net_short_return") is not None and metrics["bottom_decile_net_short_return"] <= thresholds["warn_short_leg_net_return_lte"]:
        warnings.append("short_leg_net_return_non_positive")
    if metrics.get("warnings"):
        warnings.extend([f"metrics_warning:{w}" for w in metrics["warnings"]])
    score = metrics.get("score", {}) or {}
    max_abs_score = max(abs(score.get("min", 0) or 0), abs(score.get("max", 0) or 0))
    if max_abs_score > thresholds["warn_abs_score_extreme_above"]:
        warnings.append("extreme_prediction_score")
    if metrics.get("long_short_net_return") is not None and 0 < metrics["long_short_net_return"] < thresholds["warn_long_short_net_return_below"]:
        warnings.append("long_short_net_return_positive_but_small")
    if metrics.get("mean_daily_rank_ic") is not None and metrics["mean_daily_rank_ic"] < thresholds["warn_mean_daily_rank_ic_below"]:
        warnings.append("mean_daily_rank_ic_below_0_05")

    status = "FAIL" if failures else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return {
        "gate_name": "baseline_h5_research_gate",
        "status": status,
        "passed": status != "FAIL",
        "warnings": sorted(set(warnings)),
        "failures": failures,
        "metrics_used": {
            "total_oos_rows": metrics.get("total_oos_rows"),
            "fold_count": metrics.get("fold_count"),
            "mean_daily_rank_ic": metrics.get("mean_daily_rank_ic"),
            "rank_ic_t_stat": metrics.get("rank_ic_t_stat"),
            "long_short_net_return": metrics.get("long_short_net_return"),
            "top_decile_net_return": metrics.get("top_decile_net_return"),
            "bottom_decile_net_short_return": metrics.get("bottom_decile_net_short_return"),
            "score_min": score.get("min"),
            "score_max": score.get("max"),
        },
        "thresholds": thresholds,
        "recommendation": "proceed_to_feature_expansion" if status != "FAIL" else "stop_and_inspect_pipeline_model_data",
        "next_stage": "feature_expansion" if status != "FAIL" else None,
    }


def run_baseline_gate(paths: ProjectPaths | None = None) -> dict[str, Any]:
    p = paths or project_paths()
    thresholds = load_gate_config()
    metrics, failures = load_metrics(p.metrics_reports / "baseline_h5_metrics_summary.json")
    result = evaluate_baseline_gate(metrics, thresholds, failures)
    p.gates_reports.mkdir(parents=True, exist_ok=True)
    (p.gates_reports / "baseline_h5_gate.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result
