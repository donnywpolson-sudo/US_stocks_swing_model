from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.linear_model import Ridge

from scripts.phase7_wfa.baseline_wfa import _fit_transform_train_only, load_model_config, validate_feature_cols
from scripts.project_config import ProjectPaths, project_paths
from scripts.execution import assign_score_buckets
from scripts.phase4_features.features_baseline import _baseline_h5_scoring_path, run_baseline_scoring_features


SCORING_PROXY_COLUMNS = ["median_dollar_volume_60", "zero_volume_count_60", "history_bars"]
CANDIDATE_EXPORT_TYPE = "future_daily_underlying_signal_review"
CANDIDATE_COLUMNS = [
    "score_date",
    "ticker",
    "raw_ticker",
    "pred_score_5d",
    "pred_rank_pct_by_date",
    "pred_long_rank_5d",
    "pred_short_rank_5d",
    "signal_side",
    "signal_decile",
    "close",
    "volume",
    "dollar_volume",
    "median_dollar_volume_60",
    "zero_volume_count_60",
    "history_bars",
    "passes_option_underlying_proxy_25m",
    "passes_option_underlying_proxy_50m",
    "options_liquidity_verified",
    "candidate_export_type",
]


@dataclass(frozen=True)
class DailySignalResult:
    candidates: pd.DataFrame
    summary: dict[str, object]


def _signals_reports_path(p: ProjectPaths) -> Path:
    return p.signals_reports or p.repo_root / "reports" / "signals"


def _load_json_list(path: Path) -> list[str]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_side(decile: pd.Series) -> pd.Series:
    return decile.map({10: "bullish_candidate", 1: "bearish_candidate"})


def build_daily_underlying_signals(
    train_matrix: pd.DataFrame,
    scoring_matrix: pd.DataFrame,
    *,
    feature_cols: list[str],
    target_cols: list[str],
    metadata_cols: list[str],
    excluded_cols: list[str],
    model_cfg: dict[str, Any],
) -> DailySignalResult:
    validate_feature_cols(feature_cols, target_cols, excluded_cols, metadata_cols)
    target_col = str(model_cfg["target_column"])
    if target_col not in train_matrix.columns:
        raise ValueError(f"missing target column in training matrix: {target_col}")

    missing_score_cols = sorted(set(["date", "ticker", "raw_ticker", "model_eligible", *SCORING_PROXY_COLUMNS, *feature_cols]) - set(scoring_matrix.columns))
    if missing_score_cols:
        raise ValueError(f"missing scoring matrix columns: {missing_score_cols}")

    train = train_matrix.copy()
    score = scoring_matrix.copy()
    train["date"] = pd.to_datetime(train["date"])
    score["date"] = pd.to_datetime(score["date"])
    score_date = score["date"].max()
    score = score[(score["date"] == score_date) & (score["model_eligible"] == True)].copy()
    train = train[(train["date"] < score_date) & train[target_col].notna()].copy()

    if train.empty:
        raise ValueError("no training rows before score_date")
    if score.empty:
        raise ValueError("no model-eligible scoring rows for score_date")
    if set(train["date"]).intersection(set(score["date"])):
        raise ValueError("train/score date overlap")

    x_train, x_score = _fit_transform_train_only(train, score, feature_cols)
    y_train = train[target_col].astype("float64").to_numpy()
    model = Ridge(alpha=float(model_cfg.get("ridge_alpha", 1.0)))
    model.fit(x_train, y_train)

    pred = score[["date", "ticker", "raw_ticker", "close", "volume", "dollar_volume", *SCORING_PROXY_COLUMNS]].copy()
    pred["pred_score_5d"] = model.predict(x_score)
    pred["pred_rank_pct_by_date"] = pred.groupby("date")["pred_score_5d"].rank(pct=True, method="average")
    pred["pred_long_rank_5d"] = pred.groupby("date")["pred_score_5d"].rank(ascending=False, method="first").astype("int64")
    pred["pred_short_rank_5d"] = pred.groupby("date")["pred_score_5d"].rank(ascending=True, method="first").astype("int64")
    pred["signal_decile"] = assign_score_buckets(pred, 10)
    candidates = pred.loc[pred["signal_decile"].isin([1, 10])].copy()
    candidates["signal_side"] = _candidate_side(candidates["signal_decile"])
    candidates["passes_option_underlying_proxy_25m"] = (
        (candidates["close"] >= 10)
        & (candidates["median_dollar_volume_60"] >= 25_000_000)
        & (candidates["zero_volume_count_60"] == 0)
        & (candidates["history_bars"] >= 252)
    )
    candidates["passes_option_underlying_proxy_50m"] = (
        (candidates["close"] >= 10)
        & (candidates["median_dollar_volume_60"] >= 50_000_000)
        & (candidates["zero_volume_count_60"] == 0)
        & (candidates["history_bars"] >= 252)
    )
    candidates["options_liquidity_verified"] = False
    candidates["candidate_export_type"] = CANDIDATE_EXPORT_TYPE
    candidates["score_date"] = candidates["date"].dt.date
    candidates = candidates[CANDIDATE_COLUMNS].sort_values(
        ["signal_decile", "pred_score_5d", "ticker"],
        kind="mergesort",
    ).reset_index(drop=True)

    by_side = (
        candidates.groupby("signal_side", sort=True)
        .agg(
            rows=("ticker", "size"),
            proxy_25m=("passes_option_underlying_proxy_25m", "sum"),
            proxy_50m=("passes_option_underlying_proxy_50m", "sum"),
        )
        .reset_index()
        .to_dict(orient="records")
    )
    summary = {
        "candidate_export_type": CANDIDATE_EXPORT_TYPE,
        "model_name": model_cfg.get("model_name"),
        "model_type": model_cfg.get("model_type"),
        "model_persisted": False,
        "model_artifact_path": None,
        "target_column": target_col,
        "feature_count": int(len(feature_cols)),
        "train_start_date": str(train["date"].min().date()),
        "train_end_date": str(train["date"].max().date()),
        "score_date": str(score_date.date()),
        "train_rows": int(len(train)),
        "score_rows": int(len(score)),
        "candidate_rows": int(len(candidates)),
        "missing_proxy_counts": {col: int(candidates[col].isna().sum()) for col in SCORING_PROXY_COLUMNS},
        "options_liquidity_verified_true_rows": int(candidates["options_liquidity_verified"].sum()),
        "counts_by_side": by_side,
        "blockers": [],
        "warnings": [],
        "caveats": [
            "Generated candidates are underlying signal review rows, not trade recommendations.",
            "Options liquidity cannot be validated from Stooq OHLCV alone.",
            "No option P&L, IV, Greeks, DTE, strike, expiration, bid/ask, volume, or open interest is modeled.",
        ],
    }
    return DailySignalResult(candidates=candidates, summary=summary)


def run_daily_underlying_signals(
    *,
    paths: ProjectPaths | None = None,
    score_date: str | None = None,
    rebuild_scoring: bool = True,
) -> dict[str, object]:
    p = paths or project_paths()
    if rebuild_scoring:
        run_baseline_scoring_features(paths=p, score_date=score_date)

    train_path = p.feature_matrix_baseline_h5 / "baseline_h5.parquet"
    scoring_path = _baseline_h5_scoring_path(p) / "baseline_h5_scoring.parquet"
    if not train_path.exists():
        raise FileNotFoundError(f"missing training feature matrix: {train_path}")
    if not scoring_path.exists():
        raise FileNotFoundError(f"missing scoring feature matrix: {scoring_path}")

    feature_cols = _load_json_list(p.feature_matrix_baseline_h5 / "feature_cols.json")
    target_cols = _load_json_list(p.feature_matrix_baseline_h5 / "target_cols.json")
    metadata_cols = _load_json_list(p.feature_matrix_baseline_h5 / "metadata_cols.json")
    excluded_cols = _load_json_list(p.feature_matrix_baseline_h5 / "excluded_cols.json")
    model_cfg = load_model_config()

    train_cols = sorted(set(feature_cols + ["date", "ticker", "raw_ticker", model_cfg["target_column"]]))
    score_cols = sorted(set(feature_cols + ["date", "ticker", "raw_ticker", "model_eligible", "close", "volume", "dollar_volume", *SCORING_PROXY_COLUMNS]))
    train = pd.read_parquet(train_path, columns=train_cols)
    score = pd.read_parquet(scoring_path, columns=score_cols)
    result = build_daily_underlying_signals(
        train,
        score,
        feature_cols=feature_cols,
        target_cols=target_cols,
        metadata_cols=metadata_cols,
        excluded_cols=excluded_cols,
        model_cfg=model_cfg,
    )

    signal_dir = _signals_reports_path(p)
    signal_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = signal_dir / "baseline_h5_daily_underlying_candidates.csv"
    summary_path = signal_dir / "baseline_h5_daily_underlying_signal_summary.json"
    result.candidates.to_csv(candidate_path, index=False)
    summary = {
        **result.summary,
        "candidate_output_path": str(candidate_path),
        "summary_output_path": str(summary_path),
        "training_feature_matrix_path": str(train_path),
        "scoring_feature_matrix_path": str(scoring_path),
        "baseline_model_config_path": "configs/baseline_model.yaml",
        "baseline_feature_config_path": "configs/baseline_features.yaml",
        "project_config_path": "configs/project.yaml",
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-date", default=None, help="Optional YYYY-MM-DD score date. Defaults to latest model-eligible date.")
    parser.add_argument("--no-rebuild-scoring", action="store_true", help="Reuse existing baseline_h5 scoring matrix.")
    return parser.parse_args()
