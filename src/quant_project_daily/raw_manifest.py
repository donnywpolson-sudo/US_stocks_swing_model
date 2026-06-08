from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from quant_project_daily.config import ensure_parent, project_paths
from quant_project_daily.raw_validation import clean_ticker, read_raw_txt


MANIFEST_COLUMNS = [
    "source_file",
    "raw_ticker",
    "ticker",
    "file_size_bytes",
    "row_count",
    "min_date",
    "max_date",
    "sha256",
    "parse_status",
    "error_message",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _line_count_ex_header(path: Path) -> int:
    with path.open("rb") as f:
        count = sum(1 for _ in f)
    return max(count - 1, 0)


def manifest_row(path: Path) -> dict[str, object]:
    row = {
        "source_file": path.name,
        "raw_ticker": "",
        "ticker": path.stem.upper(),
        "file_size_bytes": path.stat().st_size,
        "row_count": _line_count_ex_header(path),
        "min_date": None,
        "max_date": None,
        "sha256": sha256_file(path),
        "parse_status": "ok",
        "error_message": "",
    }
    try:
        df = read_raw_txt(path)
        missing = [c for c in ["ticker", "date"] if c not in df.columns]
        if missing:
            raise ValueError(f"missing columns: {missing}")
        if not df.empty:
            raw_ticker = str(df["ticker"].iloc[0]).strip().upper()
            dates = pd.to_datetime(df["date"].astype(str).str.strip(), format="%Y%m%d", errors="coerce")
            row.update(
                {
                    "raw_ticker": raw_ticker,
                    "ticker": clean_ticker(raw_ticker),
                    "min_date": dates.min().date().isoformat() if dates.notna().any() else None,
                    "max_date": dates.max().date().isoformat() if dates.notna().any() else None,
                }
            )
    except Exception as exc:
        row["parse_status"] = "error"
        row["error_message"] = str(exc)
    return row


def _log_manifest_progress(processed: int, rows: list[dict[str, object]], started: float) -> None:
    parse_ok = sum(1 for row in rows if row["parse_status"] == "ok")
    parse_error = sum(1 for row in rows if row["parse_status"] == "error")
    rows_total = sum(int(row["row_count"]) for row in rows)
    elapsed = time.perf_counter() - started
    print(
        f"[stage02] files_processed={processed} parse_ok={parse_ok} "
        f"parse_error={parse_error} rows_total={rows_total} elapsed_seconds={elapsed:.1f}",
        flush=True,
    )


def build_manifest(limit: int | None = None, progress_every: int | None = None) -> pd.DataFrame:
    paths = project_paths()
    files = sorted(paths.raw_txt.glob("*.txt"))
    if limit is not None:
        files = files[:limit]
    rows = []
    started = time.perf_counter()
    for i, path in enumerate(files, start=1):
        rows.append(manifest_row(path))
        if progress_every and i % progress_every == 0:
            _log_manifest_progress(i, rows, started)
    return pd.DataFrame(rows, columns=MANIFEST_COLUMNS)


def write_manifest(df: pd.DataFrame) -> dict[str, object]:
    paths = project_paths()
    ensure_parent(paths.raw_manifest)
    paths.validation_reports.mkdir(parents=True, exist_ok=True)
    df.to_parquet(paths.raw_manifest, index=False)
    summary = {
        "files_scanned": int(len(df)),
        "parse_ok": int((df["parse_status"] == "ok").sum()) if not df.empty else 0,
        "parse_error": int((df["parse_status"] == "error").sum()) if not df.empty else 0,
        "rows_total": int(df["row_count"].sum()) if not df.empty else 0,
        "output_path": str(paths.raw_manifest),
    }
    (paths.validation_reports / "raw_manifest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_manifest(limit: int | None = None, progress_every: int | None = 250) -> dict[str, object]:
    return write_manifest(build_manifest(limit=limit, progress_every=progress_every))
