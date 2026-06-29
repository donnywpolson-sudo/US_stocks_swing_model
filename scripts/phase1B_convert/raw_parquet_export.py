from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase1A_download.alpha_vantage_listing_status import DEFAULT_OUTPUT_PATH as ALPHA_VANTAGE_LISTING_STATUS_CSV
from scripts.project_config import REPO_ROOT, project_paths
from scripts.phase1C_validate.raw_validation import RAW_COLUMNS, clean_ticker, normalize_time_value, read_raw_txt


STOOQ_PARQUET_DIR = REPO_ROOT / "data" / "raw_parquet"
ALPHA_VANTAGE_PARQUET_PATH = REPO_ROOT / "data" / "reference" / "alpha_vantage_listing_status.parquet"
SUMMARY_PATH = REPO_ROOT / "reports" / "validation" / "raw_parquet_export_summary.json"
STOOQ_PARQUET_COLUMNS = (
    "raw_ticker",
    "ticker",
    "market",
    "market_year",
    "per",
    "date",
    "time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "openint",
    "year",
    "source_file",
)


def _market_from_raw_ticker(raw_ticker: object) -> str:
    text = str(raw_ticker).strip().upper()
    parts = text.rsplit(".", 1)
    return parts[1] if len(parts) == 2 and parts[1] else "UNKNOWN"


def _safe_path_part(value: object) -> str:
    text = str(value).strip().upper()
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text) or "UNKNOWN"


def raw_txt_to_parquet_frame(path: Path) -> pd.DataFrame:
    df = read_raw_txt(path)
    missing = [col for col in RAW_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{path.name} missing required columns: {', '.join(missing)}")
    out = df[RAW_COLUMNS].copy()
    out["raw_ticker"] = out["ticker"].astype(str).str.strip().str.upper()
    out["ticker"] = out["raw_ticker"].map(clean_ticker)
    out["market"] = out["raw_ticker"].map(_market_from_raw_ticker)
    out["date"] = pd.to_datetime(out["date"].astype(str).str.strip(), format="%Y%m%d", errors="raise").dt.date
    out["time"] = out["time"].map(normalize_time_value)
    out["year"] = pd.to_datetime(out["date"]).dt.year.astype("int64")
    out["market_year"] = out["market"].astype(str) + "-" + out["year"].astype(str)
    for col in ("open", "high", "low", "close", "vol", "openint"):
        out[col] = pd.to_numeric(out[col], errors="raise")
    out["volume"] = out["vol"]
    out["source_file"] = path.name
    return out.sort_values(["market", "year", "date", "time"], kind="mergesort").reset_index(drop=True)[list(STOOQ_PARQUET_COLUMNS)]


def export_stooq_raw_txt_to_parquet(
    *,
    input_dir: Path | None = None,
    output_dir: Path = STOOQ_PARQUET_DIR,
    limit: int | None = None,
    progress_every: int | None = 250,
) -> dict[str, Any]:
    source_dir = input_dir or project_paths().raw_txt
    files = sorted(source_dir.glob("*.txt"))
    if limit is not None:
        files = files[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    files_written = 0
    parse_errors: list[dict[str, str]] = []
    started = time.perf_counter()
    for index, path in enumerate(files, start=1):
        try:
            frame = raw_txt_to_parquet_frame(path)
            if not frame.empty:
                parquet_path = output_dir / f"{_safe_path_part(frame['ticker'].iloc[0])}.parquet"
                frame.to_parquet(parquet_path, index=False)
                rows_written += int(len(frame))
                files_written += 1
        except Exception as exc:
            parse_errors.append({"source_file": path.name, "error": str(exc)})
        if progress_every and index % progress_every == 0:
            elapsed = time.perf_counter() - started
            print(f"[raw-parquet] files_processed={index} files_written={files_written} rows_written={rows_written} parse_errors={len(parse_errors)} elapsed_seconds={elapsed:.1f}", flush=True)
    return {
        "input_path": str(source_dir),
        "output_path": str(output_dir),
        "files_scanned": len(files),
        "files_written": files_written,
        "rows_written": rows_written,
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors[:25],
        "layout": "one flat parquet file per stock under output_path, rows sorted by market/year/date/time",
    }


def export_alpha_vantage_listing_status_to_parquet(
    *,
    input_csv: Path = ALPHA_VANTAGE_LISTING_STATUS_CSV,
    output_path: Path = ALPHA_VANTAGE_PARQUET_PATH,
) -> dict[str, Any]:
    if not input_csv.exists():
        return {"input_path": str(input_csv), "output_path": str(output_path), "input_exists": False, "rows_written": 0, "status_counts": {}, "query_state_counts": {}}
    df = pd.read_csv(input_csv, dtype=str, keep_default_na=False)
    for col in ("ipoDate", "delistingDate", "source_asof_date"):
        if col in df.columns:
            parsed = pd.to_datetime(df[col].mask(df[col].isin(["", "null", "None"])), errors="coerce")
            df[f"{col}_year"] = parsed.dt.year.astype("Int64")
    sort_cols = [col for col in ("query_state", "status", "symbol", "ipoDate", "delistingDate") if col in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return {
        "input_path": str(input_csv),
        "output_path": str(output_path),
        "input_exists": True,
        "rows_written": int(len(df)),
        "status_counts": df["status"].value_counts(dropna=False).sort_index().to_dict() if "status" in df.columns else {},
        "query_state_counts": df["query_state"].value_counts(dropna=False).sort_index().to_dict() if "query_state" in df.columns else {},
    }


def run_raw_parquet_export(*, limit: int | None = None, progress_every: int | None = 250) -> dict[str, Any]:
    summary = {
        "stooq_raw_ohlcv": export_stooq_raw_txt_to_parquet(limit=limit, progress_every=progress_every),
        "alpha_vantage_listing_status": export_alpha_vantage_listing_status_to_parquet(),
        "guardrails": [
            "Read-only access to data/raw_txt; raw text files are not mutated.",
            "Alpha Vantage listing status remains supplemental evidence and does not clear CRSP/WRDS-style PIT.",
            "No WFA, model, target-builder, feature-builder, gate, or pipeline stage is run by this exporter.",
        ],
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary
