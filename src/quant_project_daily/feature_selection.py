from __future__ import annotations

import json
from typing import Any

import pandas as pd

from quant_project_daily.config import ProjectPaths, project_paths
from quant_project_daily.feature_discovery import load_feature_selection_config


def _is_leakage_col(name: str, tokens: list[str]) -> bool:
    low = name.lower()
    return any(tok in low for tok in tokens)


def _pair_corr_to_matrix(pair_corr: pd.DataFrame | None) -> pd.DataFrame | None:
    if pair_corr is None or pair_corr.empty:
        return None
    features = sorted(set(pair_corr["feature_a"]) | set(pair_corr["feature_b"]))
    corr = pd.DataFrame(0.0, index=features, columns=features)
    for feature in features:
        corr.loc[feature, feature] = 1.0
    for _, row in pair_corr.iterrows():
        corr.loc[row["feature_a"], row["feature_b"]] = float(row["max_abs_corr"])
        corr.loc[row["feature_b"], row["feature_a"]] = float(row["max_abs_corr"])
    return corr


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
    discovery_path = p.feature_reports / "expanded_h5_feature_discovery.csv"
    if not discovery_path.exists():
        raise FileNotFoundError(
            f"missing Stage21 discovery output: {discovery_path}. "
            "Run: python scripts/stage21_discover_features.py --max-folds 2"
        )
    discovery = pd.read_csv(discovery_path)
    corr_path = p.feature_reports / "expanded_h5_feature_correlations.csv"
    corr = _pair_corr_to_matrix(pd.read_csv(corr_path)) if corr_path.exists() else None
    ranking, selected, rejected, summary = select_features(discovery, cfg, corr)
    p.feature_reports.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(p.feature_reports / "expanded_h5_feature_ranking.csv", index=False)
    selected.to_csv(p.feature_reports / "expanded_h5_selected_features.csv", index=False)
    rejected.to_csv(p.feature_reports / "expanded_h5_rejected_features.csv", index=False)
    (p.feature_reports / "expanded_h5_selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def freeze_feature_set(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_feature_selection_config()
    selected_path = p.feature_reports / "expanded_h5_selected_features.csv"
    rejected_path = p.feature_reports / "expanded_h5_rejected_features.csv"
    missing = [str(x) for x in [selected_path, rejected_path] if not x.exists()]
    if missing:
        raise FileNotFoundError(
            "missing Stage22 selection output(s): "
            + ", ".join(missing)
            + ". Run: python scripts/stage22_select_features.py"
        )
    selected = pd.read_csv(selected_path)
    rejected = pd.read_csv(rejected_path)
    out = p.frozen_features_expanded_h5_v1
    out.mkdir(parents=True, exist_ok=True)
    feature_cols = selected["feature"].tolist()
    (out / "feature_cols.json").write_text(json.dumps(feature_cols, indent=2), encoding="utf-8")
    selected.to_csv(out / "selected_features.csv", index=False)
    rejected.to_csv(out / "rejected_features.csv", index=False)
    manifest = {
        "feature_set": cfg["version"],
        "source_matrix": str(p.feature_matrix_expanded_h5 / "expanded_h5.parquet"),
        "selection_config": cfg,
        "selected_feature_count": int(len(selected)),
        "rejected_count": int(len(rejected)),
        "caveat": "research-selected using train-fold-only discovery, not production approval",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest
