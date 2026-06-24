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

MANUAL_TEMPLATE_COLUMNS = [
    "snapshot_date",
    "snapshot_time",
    "underlying",
    "expiration",
    "dte",
    "option_type",
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
    "source",
    "source_symbol",
]

MANUAL_TEMPLATE_COLUMN_MAP = {
    "snapshot_date": "snapshot_date",
    "underlying": "underlying_ticker",
    "expiration": "expiration",
    "dte": "DTE",
    "option_type": "call_put",
    "strike": "strike",
    "bid": "bid",
    "ask": "ask",
    "mid": "mid",
    "last": "last",
    "volume": "volume",
    "open_interest": "open_interest",
    "implied_volatility": "implied_volatility",
    "delta": "delta",
    "gamma": "gamma",
    "theta": "theta",
    "vega": "vega",
    "source": "data_source",
    "source_symbol": "option_symbol",
}

MANUAL_SNAPSHOT_MANIFEST_COLUMNS = [
    "file_path",
    "underlying",
    "snapshot_date",
    "snapshot_time",
    "source",
    "notes",
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


def _manual_template_to_import_schema(raw: pd.DataFrame) -> pd.DataFrame:
    if set(CORE_REQUIRED_COLUMNS).issubset(raw.columns):
        return raw.copy()
    if not set(MANUAL_TEMPLATE_COLUMNS).issubset(raw.columns):
        return raw.copy()

    df = raw.rename(columns=MANUAL_TEMPLATE_COLUMN_MAP).copy()
    snapshot_time = _normalize_text_col(raw["snapshot_time"])
    snapshot_date = _normalize_text_col(raw["snapshot_date"])
    df["snapshot_timestamp"] = (snapshot_date + " " + snapshot_time).where(snapshot_time.notna(), pd.NA)
    return df


def _required_text(value: Any, field: str, row_number: int) -> str:
    if pd.isna(value):
        raise ValueError(f"manifest row {row_number} missing {field}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"manifest row {row_number} missing {field}")
    return text


def _optional_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _resolve_manifest_file_path(file_path: str, repo_root: Path) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    repo_relative = repo_root / path
    if repo_relative.exists():
        return repo_relative
    return Path.cwd() / path


def _read_manual_snapshot_manifest(manifest_csv: Path, repo_root: Path) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_csv)
    columns = list(manifest.columns)
    if columns != MANUAL_SNAPSHOT_MANIFEST_COLUMNS:
        raise ValueError(
            "manual snapshot manifest columns must be exactly "
            f"{MANUAL_SNAPSHOT_MANIFEST_COLUMNS}; got {columns}"
        )
    if manifest.empty:
        raise ValueError("manual snapshot manifest is empty")

    normalized_rows = []
    seen_paths: set[str] = set()
    for idx, row in manifest.iterrows():
        row_number = int(idx) + 2
        file_path_text = _required_text(row["file_path"], "file_path", row_number)
        if file_path_text in seen_paths:
            raise ValueError(f"duplicate manifest file_path: {file_path_text}")
        seen_paths.add(file_path_text)
        resolved_path = _resolve_manifest_file_path(file_path_text, repo_root)
        if not resolved_path.exists():
            raise FileNotFoundError(f"missing manifest option-chain CSV: {resolved_path}")

        snapshot_date = pd.to_datetime(_required_text(row["snapshot_date"], "snapshot_date", row_number), errors="coerce")
        if pd.isna(snapshot_date):
            raise ValueError(f"manifest row {row_number} has invalid snapshot_date")
        normalized_rows.append(
            {
                "manifest_row": row_number,
                "file_path": file_path_text,
                "resolved_path": resolved_path,
                "underlying": _required_text(row["underlying"], "underlying", row_number).upper(),
                "snapshot_date": snapshot_date.date(),
                "snapshot_time": _optional_text(row["snapshot_time"]),
                "source": _required_text(row["source"], "source", row_number),
                "notes": _optional_text(row["notes"]),
            }
        )
    return pd.DataFrame(normalized_rows)


def _validate_manifest_row_matches_snapshot(row: pd.Series) -> None:
    raw = pd.read_csv(row["resolved_path"])
    normalized, _ = normalize_option_chain_snapshot(raw)

    underlying_values = sorted(normalized["underlying_ticker"].dropna().unique().tolist())
    if underlying_values != [row["underlying"]]:
        raise ValueError(
            f"manifest row {row['manifest_row']} underlying mismatch: "
            f"manifest={row['underlying']} snapshot={underlying_values}"
        )

    snapshot_dates = sorted(normalized["snapshot_date"].dropna().unique().tolist())
    if snapshot_dates != [row["snapshot_date"]]:
        raise ValueError(
            f"manifest row {row['manifest_row']} snapshot_date mismatch: "
            f"manifest={row['snapshot_date']} snapshot={snapshot_dates}"
        )

    sources = sorted(normalized["data_source"].dropna().unique().tolist())
    if sources != [row["source"]]:
        raise ValueError(
            f"manifest row {row['manifest_row']} source mismatch: "
            f"manifest={row['source']} snapshot={sources}"
        )

    if row["snapshot_time"]:
        manifest_time = pd.to_datetime(row["snapshot_time"], errors="coerce")
        if pd.isna(manifest_time):
            raise ValueError(f"manifest row {row['manifest_row']} has invalid snapshot_time")
        snapshot_times = sorted(
            normalized["snapshot_timestamp"].dropna().dt.strftime("%H:%M:%S").unique().tolist()
        )
        expected_time = manifest_time.strftime("%H:%M:%S")
        if snapshot_times != [expected_time]:
            raise ValueError(
                f"manifest row {row['manifest_row']} snapshot_time mismatch: "
                f"manifest={expected_time} snapshot={snapshot_times}"
            )


def normalize_option_chain_snapshot(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    raw = _manual_template_to_import_schema(raw)
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
    if ((df["volume"] < 0) | (df["open_interest"] < 0)).any():
        raise ValueError("volume and open_interest must be non-negative when present")
    if (df["ask"] < df["bid"]).any():
        raise ValueError("ask must be greater than or equal to bid")

    df["mid"] = df["mid"].fillna((df["bid"] + df["ask"]) / 2.0)
    computed_dte = (pd.to_datetime(df["expiration"]) - pd.to_datetime(df["snapshot_date"])).dt.days
    if (computed_dte <= 0).any():
        raise ValueError("expiration must be after snapshot_date")
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


def _candidate_coverage(
    linked_frames: list[pd.DataFrame],
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    missing_candidate_cols = sorted(set(CANDIDATE_LINK_COLUMNS) - set(candidates.columns))
    if missing_candidate_cols:
        raise ValueError(f"missing Stage 16 candidate columns: {missing_candidate_cols}")

    coverage = candidates[CANDIDATE_LINK_COLUMNS].copy()
    coverage["ticker"] = coverage["ticker"].astype(str).str.upper().str.strip()

    if linked_frames:
        linked = pd.concat(linked_frames, ignore_index=True)
    else:
        linked = pd.DataFrame(columns=OPTION_CHAIN_SCHEMA + CANDIDATE_LINK_COLUMNS + ["snapshot_matches_score_date"])

    linked["underlying_ticker"] = linked["underlying_ticker"].astype("string").str.upper().str.strip()
    candidate_tickers = set(coverage["ticker"].dropna())
    chain_tickers = set(linked["underlying_ticker"].dropna())
    linked_to_candidates = linked[linked["ticker"].notna()].copy() if "ticker" in linked.columns else linked.iloc[0:0].copy()

    if linked_to_candidates.empty:
        stats = pd.DataFrame(
            columns=[
                "ticker",
                "snapshot_count",
                "contract_row_count",
                "snapshot_dates",
                "latest_snapshot_date",
                "snapshot_matches_score_date_any",
            ]
        )
    else:
        stats = (
            linked_to_candidates.groupby("ticker", as_index=False)
            .agg(
                snapshot_count=("snapshot_date", lambda s: int(len(set(str(x) for x in s.dropna())))),
                contract_row_count=("option_symbol", "size"),
                snapshot_dates=("snapshot_date", lambda s: "|".join(sorted(set(str(x) for x in s.dropna())))),
                latest_snapshot_date=("snapshot_date", lambda s: max(str(x) for x in s.dropna())),
                snapshot_matches_score_date_any=("snapshot_matches_score_date", lambda s: bool(s.fillna(False).any())),
            )
        )

    coverage = coverage.merge(stats, on="ticker", how="left")
    coverage["snapshot_count"] = coverage["snapshot_count"].fillna(0).astype(int)
    coverage["contract_row_count"] = coverage["contract_row_count"].fillna(0).astype(int)
    coverage["snapshot_dates"] = coverage["snapshot_dates"].fillna("")
    coverage["latest_snapshot_date"] = coverage["latest_snapshot_date"].fillna("")
    coverage["snapshot_matches_score_date_any"] = coverage["snapshot_matches_score_date_any"].fillna(False).astype(bool)
    coverage["options_liquidity_verified"] = False

    covered_tickers = set(coverage.loc[coverage["contract_row_count"] > 0, "ticker"])
    candidate_tickers_without_chain_rows = sorted(candidate_tickers - covered_tickers)
    chain_tickers_not_in_candidates = sorted(chain_tickers - candidate_tickers)
    linked_rows = int(linked["ticker"].notna().sum()) if "ticker" in linked.columns else 0
    unlinked_rows = int(linked["ticker"].isna().sum()) if "ticker" in linked.columns else int(len(linked))
    mismatch_rows = int(
        (
            linked["ticker"].notna()
            & ~linked["snapshot_matches_score_date"].fillna(False).astype(bool)
        ).sum()
    ) if "ticker" in linked.columns and "snapshot_matches_score_date" in linked.columns else 0
    summary = {
        "candidate_tickers": int(len(candidate_tickers)),
        "candidate_tickers_covered": int(len(covered_tickers)),
        "candidate_tickers_without_chain_rows_count": int(len(candidate_tickers_without_chain_rows)),
        "candidate_tickers_without_chain_rows": candidate_tickers_without_chain_rows,
        "option_chain_tickers": int(len(chain_tickers)),
        "option_chain_tickers_not_in_candidates_count": int(len(chain_tickers_not_in_candidates)),
        "option_chain_tickers_not_in_candidates": chain_tickers_not_in_candidates,
        "linked_rows": linked_rows,
        "unlinked_option_rows": unlinked_rows,
        "snapshot_matches_score_date_rows": int(linked["snapshot_matches_score_date"].fillna(False).sum()) if "snapshot_matches_score_date" in linked.columns else 0,
        "snapshot_score_date_mismatch_linked_rows": mismatch_rows,
    }
    return coverage, summary


def _compact_file_summary(summary: dict[str, object]) -> dict[str, object]:
    linkage = summary["linkage"]
    return {
        "input_csv": summary["input_csv"],
        "raw_snapshot_output_path": summary["raw_snapshot_output_path"],
        "normalized_output_path": summary["normalized_output_path"],
        "candidate_linked_output_path": summary["candidate_linked_output_path"],
        "summary_output_path": summary["summary_output_path"],
        "input_rows": summary["input_rows"],
        "normalized_rows": summary["normalized_rows"],
        "invalid_or_quarantined_rows": summary.get("invalid_or_quarantined_rows", 0),
        "candidate_linked_rows": summary["candidate_linked_rows"],
        "snapshot_dates": summary["snapshot_dates"],
        "score_dates": summary["score_dates"],
        "snapshot_date_equals_score_date": summary["snapshot_date_equals_score_date"],
        "candidate_tickers_without_option_rows_count": len(linkage["candidate_tickers_without_option_rows"]),
        "option_chain_tickers_not_in_candidates_count": len(linkage["option_chain_tickers_not_in_candidates"]),
        "linked_rows": linkage["linked_rows"],
        "unlinked_option_rows": linkage["unlinked_option_rows"],
        "snapshot_matches_score_date_rows": linkage["snapshot_matches_score_date_rows"],
    }


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
        "invalid_or_quarantined_rows": 0,
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


def import_option_chain_manifest(
    manifest_csv: Path,
    *,
    paths: ProjectPaths | None = None,
    candidates_path: Path | None = None,
) -> dict[str, object]:
    p = paths or project_paths()
    candidate_path = candidates_path or _signal_reports_path(p) / "baseline_h5_daily_underlying_candidates.csv"
    candidates = _read_candidates(candidate_path)
    manifest = _read_manual_snapshot_manifest(manifest_csv, p.repo_root)
    reports_dir = _option_reports_path(p)
    reports_dir.mkdir(parents=True, exist_ok=True)

    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    linked_frames: list[pd.DataFrame] = []

    for _, row in manifest.iterrows():
        try:
            _validate_manifest_row_matches_snapshot(row)
            summary = import_option_chain_snapshot(
                row["resolved_path"],
                paths=p,
                candidates_path=candidate_path,
            )
            successes.append(summary)
            linked_frames.append(pd.read_csv(summary["candidate_linked_output_path"]))
        except Exception as exc:
            failures.append(
                {
                    "manifest_row": int(row["manifest_row"]),
                    "file_path": row["file_path"],
                    "underlying": row["underlying"],
                    "snapshot_date": str(row["snapshot_date"]),
                    "source": row["source"],
                    "error": str(exc),
                }
            )

    if not successes:
        failures_path = reports_dir / "stage17_manual_snapshot_batch_failures.csv"
        pd.DataFrame(failures).to_csv(failures_path, index=False)
        raise ValueError(f"manual snapshot batch produced no successful imports; failures: {failures_path}")

    coverage, coverage_summary = _candidate_coverage(linked_frames, candidates)
    coverage_path = reports_dir / "stage17_manual_snapshot_candidate_coverage.csv"
    failures_path = reports_dir / "stage17_manual_snapshot_batch_failures.csv"
    summary_path = reports_dir / "stage17_manual_snapshot_batch_summary.json"

    coverage.to_csv(coverage_path, index=False)
    pd.DataFrame(
        failures,
        columns=["manifest_row", "file_path", "underlying", "snapshot_date", "source", "error"],
    ).to_csv(failures_path, index=False)

    missing_optional_counts = {
        col: int(sum(s["missing_optional_field_counts"].get(col, 0) for s in successes))
        for col in OPTIONAL_NULLABLE_COLUMNS
    }
    batch_summary = {
        "manifest_csv": str(manifest_csv),
        "candidate_path": str(candidate_path),
        "batch_summary_output_path": str(summary_path),
        "candidate_coverage_output_path": str(coverage_path),
        "batch_failures_output_path": str(failures_path),
        "manifest_rows": int(len(manifest)),
        "succeeded_files": int(len(successes)),
        "failed_files": int(len(failures)),
        "total_input_rows": int(sum(s["input_rows"] for s in successes)),
        "total_normalized_rows": int(sum(s["normalized_rows"] for s in successes)),
        "total_candidate_linked_rows": int(sum(s["candidate_linked_rows"] for s in successes)),
        "invalid_or_quarantined_rows": int(sum(s.get("invalid_or_quarantined_rows", 0) for s in successes)),
        "missing_optional_field_counts": missing_optional_counts,
        "candidate_coverage": coverage_summary,
        "per_file_summaries": [_compact_file_summary(s) for s in successes],
        "failures": failures,
        "blockers": [],
        "warnings": [
            "Manual option snapshots are review data only.",
            "options_liquidity_verified is false unless explicit option liquidity criteria are defined later.",
            "Do not assume an option chain existed at the Stage 16 score_date unless snapshot_date matches score_date.",
            "This batch import does not validate option liquidity, profitability, execution quality, or trade readiness.",
            "Row-level quarantine is not implemented in v1; invalid files are recorded in the batch failures report.",
        ],
    }
    summary_path.write_text(json.dumps(batch_summary, indent=2, default=str), encoding="utf-8")
    return batch_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path, nargs="?")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--candidates-path", type=Path, default=None)
    args = parser.parse_args()
    if bool(args.input_csv) == bool(args.manifest):
        parser.error("provide exactly one input_csv or --manifest")
    return args
