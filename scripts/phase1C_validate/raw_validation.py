from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from scripts.project_config import ensure_parent, project_paths, reset_parquet_output_dir


RAW_COLUMNS = ["ticker", "per", "date", "time", "open", "high", "low", "close", "vol", "openint"]
VALIDATED_COLUMNS = [
    "date",
    "raw_ticker",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "openint",
    "source_file",
    "year",
]


@dataclass(frozen=True)
class ValidationResult:
    valid: pd.DataFrame
    summary: dict[str, object]
    reason_counts: Counter
    warning_counts: Counter
    rejected_rows: pd.DataFrame
    zero_volume_rows: pd.DataFrame
    split_like_gaps: pd.DataFrame


def clean_header(columns: Iterable[object]) -> list[str]:
    return [str(c).strip().strip("<>").lower() for c in columns]


def clean_ticker(raw_ticker: object) -> str:
    raw = str(raw_ticker).strip().upper()
    return raw[:-3] if raw.endswith(".US") else raw


def normalize_time_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def read_raw_txt(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = clean_header(df.columns)
    return df


def _base_summary(total_files: int) -> dict[str, object]:
    return {
        "files_scanned": total_files,
        "rows_read": 0,
        "valid_rows": 0,
        "rejected_rows": 0,
        "warning_rows": 0,
        "output_path": str(project_paths().validated),
    }


def _log_validation_progress(
    processed: int,
    parse_ok: int,
    parse_error: int,
    rows_total: int,
    started: float,
) -> None:
    elapsed = time.perf_counter() - started
    print(
        f"[stage03] files_processed={processed} parse_ok={parse_ok} "
        f"parse_error={parse_error} rows_total={rows_total} elapsed_seconds={elapsed:.1f}",
        flush=True,
    )


def validate_raw_files(files: list[Path], progress_every: int | None = None) -> ValidationResult:
    valid_frames: list[pd.DataFrame] = []
    rejected_frames: list[pd.DataFrame] = []
    zero_volume_frames: list[pd.DataFrame] = []
    split_gap_frames: list[pd.DataFrame] = []
    reason_counts: Counter = Counter()
    warning_counts: Counter = Counter()
    rows_read = 0
    parse_ok = 0
    parse_error = 0
    started = time.perf_counter()

    for i, path in enumerate(files, start=1):
        try:
            df = read_raw_txt(path)
        except Exception:
            reason_counts["file_parse_error"] += 1
            parse_error += 1
            if progress_every and i % progress_every == 0:
                _log_validation_progress(i, parse_ok, parse_error, rows_read, started)
            continue

        missing = [c for c in RAW_COLUMNS if c not in df.columns]
        if missing:
            reason_counts["missing_required_columns"] += len(df)
            rows_read += len(df)
            parse_error += 1
            if len(df):
                detail = pd.DataFrame(index=df.index)
                detail["source_file"] = path.name
                detail["raw_ticker"] = df["ticker"] if "ticker" in df.columns else ""
                detail["ticker"] = df["ticker"].map(clean_ticker) if "ticker" in df.columns else ""
                detail["date"] = df["date"] if "date" in df.columns else ""
                detail["reason"] = f"missing_required_columns:{','.join(missing)}"
                rejected_frames.append(detail)
            if progress_every and i % progress_every == 0:
                _log_validation_progress(i, parse_ok, parse_error, rows_read, started)
            continue

        df = df[RAW_COLUMNS].copy()
        rows_read += len(df)
        parse_ok += 1
        df["source_file"] = path.name
        df["raw_ticker"] = df["ticker"].astype(str).str.strip().str.upper()
        df["ticker"] = df["raw_ticker"].map(clean_ticker)
        df["parsed_date"] = pd.to_datetime(df["date"].astype(str).str.strip(), format="%Y%m%d", errors="coerce")
        df["time_norm"] = df["time"].map(normalize_time_value)

        for col in ["open", "high", "low", "close", "vol", "openint"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        invalid = pd.Series(False, index=df.index)

        checks = {
            "bad_per": df["per"].astype(str).str.strip().str.upper() != "D",
            "bad_time": df["time_norm"] != "000000",
            "bad_date": df["parsed_date"].isna(),
            "bad_numeric_ohlc": df[["open", "high", "low", "close"]].isna().any(axis=1),
            "bad_numeric_volume": df["vol"].isna(),
            "bad_ohlc_positive": (df[["open", "high", "low", "close"]] <= 0).any(axis=1),
            "bad_volume_negative": df["vol"] < 0,
            "bad_ohlc_consistency": ~(
                (df["high"] >= df[["open", "low", "close"]].max(axis=1))
                & (df["low"] <= df[["open", "high", "close"]].min(axis=1))
            ),
        }

        for reason, mask in checks.items():
            mask = mask.fillna(True)
            reason_counts[reason] += int(mask.sum())
            if mask.any():
                detail = df.loc[mask, ["source_file", "raw_ticker", "ticker", "date", "open", "high", "low", "close", "vol"]].copy()
                detail["reason"] = reason
                detail = detail.rename(columns={"vol": "volume"})
                rejected_frames.append(detail)
            invalid |= mask

        dup = df.duplicated(["ticker", "parsed_date"], keep=False) & df["parsed_date"].notna()
        reason_counts["duplicate_ticker_date"] += int(dup.sum())
        if dup.any():
            detail = df.loc[dup, ["source_file", "raw_ticker", "ticker", "date", "open", "high", "low", "close", "vol"]].copy()
            detail["reason"] = "duplicate_ticker_date"
            detail = detail.rename(columns={"vol": "volume"})
            rejected_frames.append(detail)
        invalid |= dup

        bad_openint = df["openint"].isna()
        reason_counts["bad_numeric_openint"] += int(bad_openint.sum())
        if bad_openint.any():
            detail = df.loc[bad_openint, ["source_file", "raw_ticker", "ticker", "date", "open", "high", "low", "close", "vol"]].copy()
            detail["reason"] = "bad_numeric_openint"
            detail = detail.rename(columns={"vol": "volume"})
            rejected_frames.append(detail)
        invalid |= bad_openint

        zero_vol = (df["vol"] == 0) & ~invalid
        warning_counts["zero_volume_bar"] += int(zero_vol.sum())
        if zero_vol.any():
            detail = df.loc[zero_vol, ["source_file", "raw_ticker", "ticker", "parsed_date", "open", "high", "low", "close", "vol"]].copy()
            detail["date"] = detail["parsed_date"].dt.date
            detail = detail.drop(columns=["parsed_date"]).rename(columns={"vol": "volume"})
            zero_volume_frames.append(detail)

        clean = df.loc[~invalid].copy()
        if not clean.empty:
            clean = clean.sort_values(["ticker", "parsed_date"], kind="mergesort")
            prev_close = clean.groupby("ticker")["close"].shift(1)
            gap_ratio = clean["open"] / prev_close
            split_like = (gap_ratio <= 0.55) | (gap_ratio >= 1.8)
            warning_counts["split_like_gap"] += int(split_like.fillna(False).sum())
            if split_like.fillna(False).any():
                detail = clean.loc[
                    split_like.fillna(False),
                    ["source_file", "raw_ticker", "ticker", "parsed_date", "open", "close"],
                ].copy()
                detail["date"] = detail["parsed_date"].dt.date
                detail["prev_close"] = prev_close.loc[detail.index].to_numpy()
                detail["gap_pct"] = ((detail["open"] / detail["prev_close"]) - 1.0) * 100.0
                detail = detail.drop(columns=["parsed_date"])
                split_gap_frames.append(detail)

            clean["date"] = clean["parsed_date"].dt.date
            clean["volume"] = clean["vol"].astype("int64")
            clean["openint"] = clean["openint"].astype("int64")
            clean["year"] = clean["parsed_date"].dt.year.astype("int64")
            valid_frames.append(clean[VALIDATED_COLUMNS])

        if progress_every and i % progress_every == 0:
            _log_validation_progress(i, parse_ok, parse_error, rows_read, started)

    valid = pd.concat(valid_frames, ignore_index=True) if valid_frames else pd.DataFrame(columns=VALIDATED_COLUMNS)
    if not valid.empty:
        valid = valid.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)

    rejected = sum(reason_counts.values()) - reason_counts["file_parse_error"]
    rejected_rows = pd.concat(rejected_frames, ignore_index=True) if rejected_frames else pd.DataFrame()
    unique_rejected_rows = int(rejected_rows["date"].drop_duplicates().count()) if not rejected_rows.empty and "date" in rejected_rows.columns else 0
    reason_event_total = int(sum(reason_counts.values()))
    summary = _base_summary(len(files))
    summary.update(
        {
            "rows_read": int(rows_read),
            "valid_rows": int(len(valid)),
            "rejected_rows": int(rejected),
            "unique_rejected_rows": unique_rejected_rows,
            "rejection_reason_event_count": reason_event_total,
            "warning_rows": int(sum(warning_counts.values())),
            "reject_reasons": dict(reason_counts),
            "warning_reasons": dict(warning_counts),
        }
    )
    zero_volume_rows = pd.concat(zero_volume_frames, ignore_index=True) if zero_volume_frames else pd.DataFrame()
    split_like_gaps = pd.concat(split_gap_frames, ignore_index=True) if split_gap_frames else pd.DataFrame()
    return ValidationResult(
        valid=valid,
        summary=summary,
        reason_counts=reason_counts,
        warning_counts=warning_counts,
        rejected_rows=rejected_rows,
        zero_volume_rows=zero_volume_rows,
        split_like_gaps=split_like_gaps,
    )


def write_validation_outputs(result: ValidationResult) -> None:
    paths = project_paths()
    paths.validation_reports.mkdir(parents=True, exist_ok=True)

    json_path = paths.validation_reports / "raw_validation_summary.json"
    csv_path = paths.validation_reports / "raw_validation_summary.csv"
    json_path.write_text(json.dumps(result.summary, indent=2, default=str), encoding="utf-8")

    rows = []
    for kind, counts in [("reject", result.reason_counts), ("warning", result.warning_counts)]:
        rows.extend({"kind": kind, "reason": reason, "count": count} for reason, count in sorted(counts.items()))
    pd.DataFrame(rows, columns=["kind", "reason", "count"]).to_csv(csv_path, index=False)

    result.rejected_rows.to_csv(paths.validation_reports / "raw_rejected_rows.csv", index=False)
    result.zero_volume_rows.to_csv(paths.validation_reports / "raw_zero_volume_rows.csv", index=False)
    result.split_like_gaps.to_csv(paths.validation_reports / "raw_split_like_gaps.csv", index=False)

    reset_parquet_output_dir(paths.validated)
    if not result.valid.empty:
        result.valid.to_parquet(paths.validated, engine="pyarrow", partition_cols=["year"], index=False)


def run_validation(limit: int | None = None) -> dict[str, object]:
    paths = project_paths()
    files = sorted(paths.raw_txt.glob("*.txt"))
    if limit is not None:
        files = files[:limit]
    result = validate_raw_files(files, progress_every=250)
    write_validation_outputs(result)
    return result.summary
