from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import yaml

from quant_project_daily.config import REPO_ROOT, ProjectPaths, project_paths


@dataclass(frozen=True)
class WfaPlanResult:
    plan: pd.DataFrame
    summary: dict[str, object]


PLAN_COLUMNS = [
    "fold_id",
    "train_start_date",
    "train_end_date",
    "purge_start_date",
    "purge_end_date",
    "test_start_date",
    "test_end_date",
    "train_date_count",
    "purged_date_count",
    "test_date_count",
    "train_row_count",
    "test_row_count",
]


def load_wfa_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / "wfa.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_feature_date_counts(feature_path: Path) -> pd.DataFrame:
    files = sorted(feature_path.rglob("*.parquet")) if feature_path.is_dir() else [feature_path]
    if not files:
        return pd.DataFrame(columns=["date", "row_count"])
    lf = pl.scan_parquet([str(f) for f in files]).select(pl.col("date").cast(pl.Date, strict=False))
    out = lf.group_by("date").len().rename({"len": "row_count"}).sort("date").collect()
    return out.to_pandas()


def build_wfa_plan(date_counts: pd.DataFrame, cfg: dict[str, Any]) -> WfaPlanResult:
    train_days = int(cfg["train_window_days"])
    test_days = int(cfg["test_window_days"])
    step_days = int(cfg["step_days"])
    purge_days = int(cfg["purge_days"])
    embargo_days = int(cfg.get("embargo_days", 0))

    warnings: list[str] = []
    if date_counts.empty:
        summary = _summary(pd.DataFrame(columns=PLAN_COLUMNS), None, None, cfg, warnings + ["missing_feature_dates"])
        return WfaPlanResult(pd.DataFrame(columns=PLAN_COLUMNS), summary)

    dc = date_counts.copy()
    dc["date"] = pd.to_datetime(dc["date"]).dt.date
    dc = dc.sort_values("date").reset_index(drop=True)
    dates = dc["date"].tolist()
    rows = dc["row_count"].astype("int64").tolist()

    first_test_idx = train_days + purge_days
    if len(dates) < first_test_idx + test_days:
        warnings.append("insufficient_history_for_full_fold")

    records = []
    fold_id = 1
    test_start_idx = first_test_idx
    while test_start_idx + test_days <= len(dates):
        train_start_idx = test_start_idx - purge_days - train_days
        train_end_idx = test_start_idx - purge_days - 1
        purge_start_idx = test_start_idx - purge_days
        purge_end_idx = test_start_idx - 1
        test_end_idx = test_start_idx + test_days - 1

        train_row_count = int(sum(rows[train_start_idx : train_end_idx + 1]))
        test_row_count = int(sum(rows[test_start_idx : test_end_idx + 1]))
        records.append(
            {
                "fold_id": fold_id,
                "train_start_date": str(dates[train_start_idx]),
                "train_end_date": str(dates[train_end_idx]),
                "purge_start_date": str(dates[purge_start_idx]) if purge_days else None,
                "purge_end_date": str(dates[purge_end_idx]) if purge_days else None,
                "test_start_date": str(dates[test_start_idx]),
                "test_end_date": str(dates[test_end_idx]),
                "train_date_count": train_days,
                "purged_date_count": purge_days,
                "test_date_count": test_days,
                "train_row_count": train_row_count,
                "test_row_count": test_row_count,
            }
        )
        fold_id += 1
        test_start_idx += step_days + embargo_days

    plan = pd.DataFrame(records, columns=PLAN_COLUMNS)
    summary = _summary(plan, str(dates[0]), str(dates[-1]), cfg, warnings)
    return WfaPlanResult(plan, summary)


def _summary(
    plan: pd.DataFrame,
    min_date: str | None,
    max_date: str | None,
    cfg: dict[str, Any],
    warnings: list[str],
) -> dict[str, object]:
    return {
        "total_folds": int(len(plan)),
        "min_feature_date": min_date,
        "max_feature_date": max_date,
        "train_window_days": int(cfg["train_window_days"]),
        "test_window_days": int(cfg["test_window_days"]),
        "step_days": int(cfg["step_days"]),
        "purge_days": int(cfg["purge_days"]),
        "embargo_days": int(cfg.get("embargo_days", 0)),
        "total_train_rows_across_folds": int(plan["train_row_count"].sum()) if not plan.empty else 0,
        "total_test_rows_across_folds": int(plan["test_row_count"].sum()) if not plan.empty else 0,
        "first_fold_dates": plan.iloc[0].to_dict() if not plan.empty else None,
        "last_fold_dates": plan.iloc[-1].to_dict() if not plan.empty else None,
        "blockers": [],
        "warnings": warnings,
    }


def run_wfa_plan(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_wfa_config()
    result = build_wfa_plan(read_feature_date_counts(p.feature_matrix_baseline_h5), cfg)
    p.wfa_reports.mkdir(parents=True, exist_ok=True)
    result.plan.to_csv(p.wfa_reports / "baseline_h5_split_plan.csv", index=False)
    (p.wfa_reports / "baseline_h5_split_summary.json").write_text(
        json.dumps(result.summary, indent=2, default=str),
        encoding="utf-8",
    )
    return result.summary
