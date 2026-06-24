from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant_project_daily.config import ProjectPaths, project_paths


OPTION_CHAIN_SCHEMA = [
    "snapshot_date",
    "snapshot_timestamp",
    "underlying_ticker",
    "underlying_price",
    "option_symbol",
    "expiration",
    "DTE",
    "strike",
    "call_put",
    "bid",
    "ask",
    "mid",
    "last",
    "volume",
    "open_interest",
    "implied_volatility",
    "delta",
    "gamma",
    "theta",
    "vega",
    "data_source",
    "data_delay_status",
    "quote_timestamp",
]

CORE_REQUIRED_COLUMNS = [
    "snapshot_date",
    "underlying_ticker",
    "option_symbol",
    "expiration",
    "strike",
    "call_put",
    "bid",
    "ask",
    "data_source",
]

OPTIONAL_NULLABLE_COLUMNS = [
    "snapshot_timestamp",
    "underlying_price",
    "DTE",
    "mid",
    "last",
    "volume",
    "open_interest",
    "implied_volatility",
    "delta",
    "gamma",
    "theta",
    "vega",
    "quote_timestamp",
    "data_delay_status",
]

CANDIDATE_LINK_COLUMNS = [
    "score_date",
    "ticker",
    "raw_ticker",
    "signal_side",
    "signal_decile",
    "pred_score_5d",
    "pred_rank_pct_by_date",
    "passes_option_underlying_proxy_25m",
    "passes_option_underlying_proxy_50m",
]


@dataclass(frozen=True)
class OptionImportResult:
    normalized: pd.DataFrame
    candidate_linked: pd.DataFrame
    summary: dict[str, object]


def _path_or_default(path: Path | None, default: Path) -> Path:
    return path if path is not None else default


def _option_normalized_path(p: ProjectPaths) -> Path:
    return _path_or_default(p.option_chain_normalized, p.repo_root / "data" / "options" / "normalized")


def _option_raw_snapshots_path(p: ProjectPaths) -> Path:
    return _path_or_default(p.option_chain_raw_snapshots, p.repo_root / "data" / "options" / "raw_snapshots")


def _option_candidate_linked_path(p: ProjectPaths) -> Path:
    return _path_or_default(p.option_chain_candidate_linked, p.repo_root / "data" / "options" / "candidate_linked")


def _option_reports_path(p: ProjectPaths) -> Path:
    return _path_or_default(p.option_chain_reports, p.repo_root / "reports" / "options")


def _signal_reports_path(p: ProjectPaths) -> Path:
    return _path_or_default(p.signals_reports, p.repo_root / "reports" / "signals")


def _coerce_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")


def _normalize_text_col(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().replace("", pd.NA)


def normalize_option_chain_snapshot(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    missing_core = sorted(set(CORE_REQUIRED_COLUMNS) - set(raw.columns))
    if missing_core:
        raise ValueError(f"missing required option-chain columns: {missing_core}")

    df = raw.copy()
    missing_optional_added = {}
    for col in OPTIONAL_NULLABLE_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
            missing_optional_added[col] = int(len(df))

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.date
    df["expiration"] = pd.to_datetime(df["expiration"], errors="coerce").dt.date
    df["snapshot_timestamp"] = pd.to_datetime(df["snapshot_timestamp"], errors="coerce")
    df["quote_timestamp"] = pd.to_datetime(df["quote_timestamp"], errors="coerce")
    df["underlying_ticker"] = _normalize_text_col(df["underlying_ticker"]).str.upper()
    df["option_symbol"] = _normalize_text_col(df["option_symbol"])
    df["data_source"] = _normalize_text_col(df["data_source"])
    df["call_put"] = _normalize_text_col(df["call_put"]).str.upper()
    df["call_put"] = df["call_put"].replace({"CALL": "C", "PUT": "P"})

    _coerce_numeric(
        df,
        [
            "underlying_price",
            "DTE",
            "strike",
            "bid",
            "ask",
            "mid",
            "last",
            "volume",
            "open_interest",
            "implied_volatility",
            "delta",
            "gamma",
            "theta",
            "vega",
        ],
    )

    if df[CORE_REQUIRED_COLUMNS].isna().any(axis=1).any():
        counts = {col: int(df[col].isna().sum()) for col in CORE_REQUIRED_COLUMNS if df[col].isna().any()}
        raise ValueError(f"required option-chain values contain nulls: {counts}")
    invalid_call_put = sorted(set(df["call_put"].dropna()) - {"C", "P"})
    if invalid_call_put:
        raise ValueError(f"invalid call_put values: {invalid_call_put}")
    if ((df["bid"] < 0) | (df["ask"] < 0) | (df["strike"] < 0)).any():
        raise ValueError("bid, ask, and strike must be non-negative")
    if (df["ask"] < df["bid"]).any():
        raise ValueError("ask must be greater than or equal to bid")

    df["mid"] = df["mid"].fillna((df["bid"] + df["ask"]) / 2.0)
    computed_dte = (pd.to_datetime(df["expiration"]) - pd.to_datetime(df["snapshot_date"])).dt.days
    df["DTE"] = df["DTE"].fillna(computed_dte)

    duplicate_cols = ["snapshot_date", "data_source", "underlying_ticker", "option_symbol", "expiration", "strike", "call_put"]
    duplicate_rows = int(df.duplicated(duplicate_cols).sum())
    if duplicate_rows:
        raise ValueError(f"duplicate option-chain rows: {duplicate_rows}")

    df = df[OPTION_CHAIN_SCHEMA].sort_values(["snapshot_date", "underlying_ticker", "expiration", "strike", "call_put", "option_symbol"]).reset_index(drop=True)
    missing_optional_counts = {col: int(df[col].isna().sum()) for col in OPTIONAL_NULLABLE_COLUMNS}
    for col, count in missing_optional_added.items():
        missing_optional_counts[col] = count
    return df, missing_optional_counts


def link_option_chains_to_candidates(chains: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    candidate_cols = [col for col in CANDIDATE_LINK_COLUMNS if col in candidates.columns]
    missing_candidate_cols = sorted(set(CANDIDATE_LINK_COLUMNS) - set(candidate_cols))
    if missing_candidate_cols:
        raise ValueError(f"missing Stage 16 candidate columns: {missing_candidate_cols}")

    c = candidates[candidate_cols].copy()
    c["ticker"] = c["ticker"].astype(str).str.upper().str.strip()
    c["score_date"] = pd.to_datetime(c["score_date"], errors="coerce").dt.date
    chain = chains.copy()
    chain["underlying_ticker"] = chain["underlying_ticker"].astype(str).str.upper().str.strip()
    linked = chain.merge(c, left_on="underlying_ticker", right_on="ticker", how="left", validate="many_to_one")
    linked["snapshot_matches_score_date"] = linked["snapshot_date"] == linked["score_date"]

    candidate_tickers = set(c["ticker"].dropna())
    chain_tickers = set(chain["underlying_ticker"].dropna())
    linkage = {
        "candidate_tickers": int(len(candidate_tickers)),
        "option_chain_tickers": int(len(chain_tickers)),
        "candidate_tickers_without_option_rows": sorted(candidate_tickers - chain_tickers),
        "option_chain_tickers_not_in_candidates": sorted(chain_tickers - candidate_tickers),
        "linked_rows": int(linked["score_date"].notna().sum()),
        "unlinked_option_rows": int(linked["score_date"].isna().sum()),
        "snapshot_matches_score_date_rows": int(linked["snapshot_matches_score_date"].fillna(False).sum()),
    }
    return linked, linkage


def _read_candidates(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing Stage 16 candidate file: {path}")
    return pd.read_csv(path)


def import_option_chain_snapshot(
    input_csv: Path,
    *,
    paths: ProjectPaths | None = None,
    candidates_path: Path | None = None,
) -> dict[str, object]:
    p = paths or project_paths()
    candidate_path = candidates_path or _signal_reports_path(p) / "baseline_h5_daily_underlying_candidates.csv"
    raw = pd.read_csv(input_csv)
    normalized, missing_optional_counts = normalize_option_chain_snapshot(raw)
    candidates = _read_candidates(candidate_path)
    linked, linkage = link_option_chains_to_candidates(normalized, candidates)

    raw_snapshot_dir = _option_raw_snapshots_path(p)
    normalized_dir = _option_normalized_path(p)
    linked_dir = _option_candidate_linked_path(p)
    reports_dir = _option_reports_path(p)
    raw_snapshot_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    linked_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    stem = input_csv.stem
    raw_snapshot_path = raw_snapshot_dir / input_csv.name
    normalized_path = normalized_dir / f"{stem}_normalized.csv"
    linked_path = linked_dir / f"{stem}_candidate_linked.csv"
    summary_path = reports_dir / f"{stem}_import_summary.json"
    if input_csv.resolve() != raw_snapshot_path.resolve():
        shutil.copy2(input_csv, raw_snapshot_path)
    normalized.to_csv(normalized_path, index=False)
    linked.to_csv(linked_path, index=False)

    snapshot_dates = sorted(str(x) for x in normalized["snapshot_date"].dropna().unique())
    score_dates = sorted(str(x) for x in linked["score_date"].dropna().unique())
    summary = {
        "input_csv": str(input_csv),
        "candidate_path": str(candidate_path),
        "raw_snapshot_output_path": str(raw_snapshot_path),
        "normalized_output_path": str(normalized_path),
        "candidate_linked_output_path": str(linked_path),
        "summary_output_path": str(summary_path),
        "schema_columns": OPTION_CHAIN_SCHEMA,
        "required_core_columns": CORE_REQUIRED_COLUMNS,
        "nullable_optional_columns": OPTIONAL_NULLABLE_COLUMNS,
        "input_rows": int(len(raw)),
        "normalized_rows": int(len(normalized)),
        "candidate_linked_rows": int(len(linked)),
        "snapshot_dates": snapshot_dates,
        "score_dates": score_dates,
        "snapshot_date_equals_score_date": bool(set(snapshot_dates) == set(score_dates)) if snapshot_dates and score_dates else False,
        "missing_optional_field_counts": missing_optional_counts,
        "linkage": linkage,
        "blockers": [],
        "warnings": [
            "Option snapshots are linked to Stage 16 candidates by underlying_ticker only.",
            "Do not assume the option chain existed at the historical score_date unless snapshot_date matches score_date.",
            "This import does not validate option liquidity, profitability, or trade suitability.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--candidates-path", type=Path, default=None)
    return parser.parse_args()
