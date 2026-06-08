from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from quant_project_daily.config import ProjectPaths, project_paths
from quant_project_daily.feature_discovery import load_feature_selection_config


def _is_leakage_col(name: str, tokens: list[str]) -> bool:
    low = name.lower()
    return any(tok in low for tok in tokens)


def _fold_ic_corr(discovery: pd.DataFrame) -> pd.DataFrame | None:
    if "fold_rank_ic_by_fold" not in discovery.columns:
        return None
    records = {}
    for _, row in discovery.iterrows():
        try:
            records[row["feature"]] = json.loads(row["fold_rank_ic_by_fold"])
        except (TypeError, json.JSONDecodeError):
            continue
    if len(records) < 2:
        return None
    return pd.DataFrame.from_dict(records, orient="index").T.astype(float).corr()


def select_features(
    discovery: pd.DataFrame,
    cfg: dict[str, Any],
    corr: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    ranked = discovery.copy()
    reasons = []
    for _, r in ranked.iterrows():
        if _is_leakage_col(str(r["feature"]), cfg["leakage_tokens"]):
            reasons.append("leakage_name")
        elif float(r["non_null_pct"]) < float(cfg["min_non_null_pct"]):
            reasons.append("excessive_nulls")
        elif float(r["finite_pct"]) < float(cfg["min_finite_pct"]):
            reasons.append("non_finite")
        elif pd.isna(r["std"]) or float(r["std"]) <= float(cfg["min_std"]):
            reasons.append("near_zero_variance")
        elif pd.isna(r["abs_mean_rank_ic"]) or float(r["abs_mean_rank_ic"]) < float(cfg["min_abs_mean_rank_ic"]):
            reasons.append("weak_rank_ic")
        elif float(r["sign_stability"]) < float(cfg["min_sign_stability"]):
            reasons.append("unstable_sign")
        else:
            reasons.append("")
    ranked["reject_reason"] = reasons
    ranked["selection_score"] = (
        ranked["abs_mean_rank_ic"].fillna(0).abs()
        * ranked["sign_stability"].fillna(0)
        * ranked["non_null_pct"].fillna(0)
    )
    ranked = ranked.sort_values(
        ["reject_reason", "selection_score", "feature"],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    selected: list[str] = []
    threshold = float(cfg["correlation_prune_threshold"])
    corr = corr if corr is not None else _fold_ic_corr(ranked)
    for _, row in ranked[ranked["reject_reason"] == ""].iterrows():
        feature = row["feature"]
        if corr is not None and selected and feature in corr.index:
            peers = [s for s in selected if s in corr.columns]
            if peers:
                max_abs_corr = corr.loc[feature, peers].abs().max()
                if pd.notna(max_abs_corr) and float(max_abs_corr) >= threshold:
                    ranked.loc[ranked["feature"] == feature, "reject_reason"] = "correlation_pruned"
                    continue
        selected.append(feature)
        if len(selected) >= int(cfg["max_selected_features"]):
            break
    ranked["selected"] = ranked["feature"].isin(selected)
    selected_df = ranked[ranked["selected"]].copy()
    rejected_df = ranked[~ranked["selected"]].copy()
    summary = {
        "features_ranked": int(len(ranked)),
        "selected_feature_count": int(len(selected_df)),
        "rejected_feature_count": int(len(rejected_df)),
        "max_selected_features": int(cfg["max_selected_features"]),
        "blockers": [],
        "warnings": [],
    }
    return ranked, selected_df, rejected_df, summary


def run_feature_selection(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_feature_selection_config()
    discovery = pd.read_csv(p.feature_reports / "expanded_h20_feature_discovery.csv")
    ranking, selected, rejected, summary = select_features(discovery, cfg)
    p.feature_reports.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(p.feature_reports / "expanded_h20_feature_ranking.csv", index=False)
    selected.to_csv(p.feature_reports / "expanded_h20_selected_features.csv", index=False)
    rejected.to_csv(p.feature_reports / "expanded_h20_rejected_features.csv", index=False)
    (p.feature_reports / "expanded_h20_selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def freeze_feature_set(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_feature_selection_config()
    selected = pd.read_csv(p.feature_reports / "expanded_h20_selected_features.csv")
    rejected = pd.read_csv(p.feature_reports / "expanded_h20_rejected_features.csv")
    out = p.frozen_features_expanded_h20_v1
    out.mkdir(parents=True, exist_ok=True)
    feature_cols = selected["feature"].tolist()
    (out / "feature_cols.json").write_text(json.dumps(feature_cols, indent=2), encoding="utf-8")
    selected.to_csv(out / "selected_features.csv", index=False)
    rejected.to_csv(out / "rejected_features.csv", index=False)
    manifest = {
        "feature_set": cfg["version"],
        "source_matrix": str(p.feature_matrix_expanded_h20 / "expanded_h20.parquet"),
        "selection_config": cfg,
        "selected_feature_count": int(len(selected)),
        "rejected_count": int(len(rejected)),
        "caveat": "research-selected using train-fold-only discovery, not production approval",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest
