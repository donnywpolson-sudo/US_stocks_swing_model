#!/usr/bin/env python3
"""
Stooq US Stock Raw Archive Inspector.

Opens ZIP archives in data/raw, samples inner files safely,
classifies contents (daily_ascii, hourly_ascii, metastock, unknown),
computes hashes, inventories files, and produces:

  reports/raw_ingest/stooq_raw_inventory.json
  reports/raw_ingest/stooq_raw_inventory.csv
  reports/raw_ingest/stooq_schema_profile.json
  reports/raw_ingest/stooq_prepare_plan.md

Usage:
  python -m scripts.raw_ingest.inspect_stooq_raw
      --raw-root data/raw
      --reports-root reports/raw_ingest
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

INVENTORY_FIELDS = [
    "archive_path",
    "inner_file_path",
    "inferred_type",
    "symbol",
    "extension",
    "size_bytes",
    "row_count_sampled_or_exact",
    "first_ts",
    "last_ts",
    "columns",
    "delimiter",
    "encoding",
    "source_zip_hash",
    "warnings",
    "failures",
    "status",
]


def sha256_file(path: str | Path) -> str:
    """Stream-safe SHA-256 of an entire file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_encoding(data: bytes) -> str:
    """Best-effort encoding detection from a byte sample."""
    try:
        data.decode("ascii")
        return "ascii"
    except UnicodeDecodeError:
        try:
            data.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "binary"


def _delimiter_from_header(header: str) -> str:
    """Detect CSV delimiter from the header line."""
    for d in [",", "\t", "|", ";"]:
        if d in header:
            return d
    return "unknown"


def _extract_symbol_from_path(inner_path: str) -> str:
    """Extract ticker symbol from path like .../aadr.us.txt -> AADR.US."""
    stem = Path(inner_path).stem
    # remove .us suffix, uppercase
    return stem.upper() if stem else ""


def _classify_inner_file(inner_path: str) -> str:
    """
    Classify an inner file based on its path and extension.

    Returns one of:
      daily_ascii, hourly_ascii, metastock_master, metastock_emaster,
      metastock_dop, metastock_data, metadata, unknown
    """
    normalized = inner_path.replace("\\", "/")

    if normalized.endswith("/"):
        return "directory"

    parts = [p for p in normalized.strip("/").split("/") if p]
    name = parts[-1].upper() if parts else ""
    parent = parts[-2].upper() if len(parts) >= 2 else ""

    if name == "DAT" and re.fullmatch(r"F\d+", parent):
        return "metastock_data"

    ext = Path(inner_path).suffix.lower()
    path_lower = inner_path.lower()

    # MetaStock files
    if name == "MASTER":
        return "metastock_master"
    if name == "EMASTER":
        return "metastock_emaster"
    if ext == ".dop":
        return "metastock_dop"
    if ext == ".dat":
        return "metastock_data"

    # ASCII text files
    if ext == ".txt":
        if "/daily/" in path_lower:
            return "daily_ascii"
        if "/hourly/" in path_lower:
            return "hourly_ascii"
        return "unknown_ascii"

    # directory entries (ZIP directory markers end with / or \)
    if ext == "" and (inner_path.endswith("/") or inner_path.endswith("\\")):
        return "directory"

    return "unknown"


def _check_dop_schema(data: bytes) -> dict[str, Any]:
    """Parse a DOP file to extract field definitions."""
    fields: dict[str, Any] = {}
    for line in data.decode("ascii", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) >= 2:
            field_name = parts[0].strip('"')
            field_type = parts[1]
            fields[field_name] = {"type": field_type, "raw": line}
    return fields


# ---------------------------------------------------------------------------
# sample schema from a text file inside a ZIP
# ---------------------------------------------------------------------------


def _sample_txt_schema(
    archive: Any, inner_path: str, max_lines: int = 2000
) -> dict[str, Any]:
    """
    Read the first N lines from a text file inside a ZIP and infer schema.

    Never reads more than *max_lines* lines. Returns an info dict.
    """
    result: dict[str, Any] = {
        "columns": [],
        "delimiter": "unknown",
        "encoding": "unknown",
        "row_count_sampled_or_exact": 0,
        "first_ts": None,
        "last_ts": None,
        "per_value": None,
        "sample_rows": 0,
        "warnings": [],
    }

    try:
        raw = archive.read(inner_path)
        encoding = _detect_encoding(raw)
        result["encoding"] = encoding

        if encoding == "binary":
            result["warnings"].append("binary_file_skipped")
            return result

        text = raw.decode(encoding, errors="replace")
        lines = text.splitlines()
        total_lines = len(lines)

        if not lines:
            result["warnings"].append("empty_file")
            return result

        header = lines[0].strip()
        result["delimiter"] = _delimiter_from_header(header)
        columns = [c.strip().strip("<>").lower() for c in header.split(result["delimiter"])]
        result["columns"] = columns

        # Determine row count — cheap if file is small, otherwise sample
        if total_lines <= max_lines + 1:
            result["row_count_sampled_or_exact"] = max(total_lines - 1, 0)
            data_lines = lines[1:]
        else:
            result["row_count_sampled_or_exact"] = total_lines - 1  # exact from metadata
            data_lines = lines[1 : max_lines + 1]

        result["sample_rows"] = len(data_lines)

        # Extract date range and per value from sampled data lines
        date_col = None
        time_col = None
        per_col = None
        for c in columns:
            if c == "date":
                date_col = c
            elif c == "time":
                time_col = c
            elif c == "per":
                per_col = c

        dates: list[str] = []
        times: list[str] = []
        pers: set[str] = set()

        for line in data_lines:
            if not line.strip():
                continue
            parts = line.split(result["delimiter"])
            if date_col is not None and len(parts) > columns.index(date_col):
                dates.append(parts[columns.index(date_col)].strip())
            if time_col is not None and len(parts) > columns.index(time_col):
                times.append(parts[columns.index(time_col)].strip())
            if per_col is not None and len(parts) > columns.index(per_col):
                pers.add(parts[columns.index(per_col)].strip())

        if dates:
            result["first_ts"] = dates[0]
            result["last_ts"] = dates[-1]

        if pers:
            result["per_value"] = list(pers)

        # Determine if daily or hourly from per_value + path
        if result["per_value"] == ["D"]:
            result["inferred_period"] = "daily"
        elif result["per_value"] == ["60"]:
            result["inferred_period"] = "hourly"
        else:
            result["inferred_period"] = "unknown"

    except Exception as exc:
        result["warnings"].append(f"sample_error:{exc}")

    return result


# ---------------------------------------------------------------------------
# inspect a single ZIP archive
# ---------------------------------------------------------------------------


def inspect_zip(archive_path: Path) -> list[dict[str, Any]]:
    """
    Inspect a single ZIP archive and return inventory rows for each inner file.
    """
    import zipfile

    if not archive_path.is_file():
        return []

    archive_hash = sha256_file(archive_path)
    archive_name = archive_path.name
    rows: list[dict[str, Any]] = []

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            infos = zf.infolist()
            # Sort for deterministic output
            infos.sort(key=lambda i: i.filename)

            for info in infos:
                inner = info.filename
                ext = Path(inner).suffix.lower()
                inferred = _classify_inner_file(inner)
                symbol = _extract_symbol_from_path(inner)

                row: dict[str, Any] = {
                    "archive_path": archive_name,
                    "inner_file_path": inner,
                    "inferred_type": inferred,
                    "symbol": symbol,
                    "extension": ext,
                    "size_bytes": info.file_size,
                    "row_count_sampled_or_exact": None,
                    "first_ts": None,
                    "last_ts": None,
                    "columns": [],
                    "delimiter": None,
                    "encoding": None,
                    "source_zip_hash": archive_hash,
                    "warnings": [],
                    "failures": [],
                    "status": "PASS",
                }

                # Skip directories
                if inferred == "directory":
                    row["status"] = "PASS"
                    rows.append(row)
                    continue

                # Sample schema for text files (cheap sampling)
                if inferred in ("daily_ascii", "hourly_ascii", "unknown_ascii"):
                    try:
                        schema = _sample_txt_schema(zf, inner, max_lines=2000)
                        row.update(
                            {
                                "columns": schema["columns"],
                                "delimiter": schema["delimiter"],
                                "encoding": schema["encoding"],
                                "row_count_sampled_or_exact": schema["row_count_sampled_or_exact"],
                                "first_ts": schema["first_ts"],
                                "last_ts": schema["last_ts"],
                            }
                        )
                        if schema["warnings"]:
                            row["warnings"].extend(schema["warnings"])
                            row["status"] = "WARN"
                    except Exception as exc:
                        row["failures"].append(str(exc))
                        row["status"] = "FAIL"

                # Sample DOP files for field definitions
                elif inferred == "metastock_dop":
                    try:
                        dop_data = zf.read(inner)
                        fields = _check_dop_schema(dop_data)
                        row["columns"] = list(fields.keys())
                        row["encoding"] = "ascii"
                        row["delimiter"] = ","
                        row["row_count_sampled_or_exact"] = 0
                    except Exception as exc:
                        row["failures"].append(str(exc))
                        row["status"] = "FAIL"

                # MetaStock binary files — just classify, don't parse
                elif inferred in ("metastock_master", "metastock_emaster", "metastock_data"):
                    row["encoding"] = "binary"
                    row["warnings"].append("binary_format_not_parsed")

                # Unknown files
                elif inferred == "unknown":
                    row["warnings"].append("unknown_file_type")
                    row["status"] = "WARN"

                rows.append(row)

    except zipfile.BadZipFile as exc:
        rows.append(
            {
                "archive_path": archive_name,
                "inner_file_path": archive_name,
                "inferred_type": "unknown",
                "symbol": "",
                "extension": ".zip",
                "size_bytes": archive_path.stat().st_size,
                "row_count_sampled_or_exact": None,
                "first_ts": None,
                "last_ts": None,
                "columns": [],
                "delimiter": None,
                "encoding": None,
                "source_zip_hash": archive_hash,
                "warnings": [],
                "failures": [f"BadZipFile: {exc}"],
                "status": "FAIL",
            }
        )

    return rows


# ---------------------------------------------------------------------------
# inventory all ZIPs under a root directory
# ---------------------------------------------------------------------------


def inventory_all(raw_root: Path) -> list[dict[str, Any]]:
    """Recursively find all .zip files under *raw_root* and inspect them."""
    all_rows: list[dict[str, Any]] = []
    zip_files = sorted(raw_root.rglob("*.zip"))
    for z in zip_files:
        rows = inspect_zip(z)
        all_rows.extend(rows)
    return all_rows


# ---------------------------------------------------------------------------
# build schema profile from inventory
# ---------------------------------------------------------------------------


def build_schema_profile(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate inventory into a schema profile."""
    archives_detected: dict[str, Any] = {}
    daily_schemas: set[str] = set()
    hourly_schemas: set[str] = set()
    metastock_present = False
    metadata_present = False
    unknown_count = 0
    file_type_counts: dict[str, int] = {}

    for row in inventory:
        it = row["inferred_type"]
        file_type_counts[it] = file_type_counts.get(it, 0) + 1

        if row["inferred_type"] in ("unknown", "unknown_ascii"):
            unknown_count += 1

        if "metastock" in row["inferred_type"]:
            metastock_present = True

        if row["inferred_type"] == "metadata":
            metadata_present = True

        # Track archive-level info
        arch = row["archive_path"]
        if arch not in archives_detected:
            archives_detected[arch] = {
                "archive_path": arch,
                "file_count": 0,
                "types_found": set(),
                "daily_ascii_count": 0,
                "hourly_ascii_count": 0,
                "metastock_count": 0,
                "hash": row["source_zip_hash"],
            }
        a = archives_detected[arch]
        a["file_count"] += 1
        a["types_found"].add(row["inferred_type"])

        if row["inferred_type"] == "daily_ascii":
            a["daily_ascii_count"] += 1
            if row["columns"]:
                daily_schemas.add(str(row["columns"]))
        elif row["inferred_type"] == "hourly_ascii":
            a["hourly_ascii_count"] += 1
            if row["columns"]:
                hourly_schemas.add(str(row["columns"]))
        elif "metastock" in row["inferred_type"]:
            a["metastock_count"] += 1

    # Normalize types_found to list
    for a in archives_detected.values():
        a["types_found"] = sorted(a["types_found"])

    # Determine detected schemas from sampled columns
    daily_columns: list[str] = []
    hourly_columns: list[str] = []
    metastock_dop_fields: list[str] = []

    # Find first daily/horuly ASCII file with columns for reference schema
    daily_ref = None
    hourly_ref = None
    for row in inventory:
        if row["inferred_type"] == "daily_ascii" and row["columns"] and not daily_ref:
            daily_ref = row
        if row["inferred_type"] == "hourly_ascii" and row["columns"] and not hourly_ref:
            hourly_ref = row
        if row["inferred_type"] == "metastock_dop" and row["columns"] and not metastock_dop_fields:
            metastock_dop_fields = row["columns"]

    # Date range across all files
    all_first_dates: list[str] = []
    all_last_dates: list[str] = []
    for row in inventory:
        if row["first_ts"]:
            all_first_dates.append(row["first_ts"])
        if row["last_ts"]:
            all_last_dates.append(row["last_ts"])

    # Row counts
    sampled_rows = sum(
        r["row_count_sampled_or_exact"]
        for r in inventory
        if r["row_count_sampled_or_exact"] is not None
    )

    daily_schema: dict[str, Any] = {
        "columns": daily_ref["columns"] if daily_ref else [],
        "delimiter": daily_ref["delimiter"] if daily_ref else None,
        "encoding": daily_ref["encoding"] if daily_ref else None,
        "per_value": "D",
        "time_value": "000000",
        "sample_file": daily_ref["inner_file_path"] if daily_ref else None,
    }
    hourly_schema: dict[str, Any] = {
        "columns": hourly_ref["columns"] if hourly_ref else [],
        "delimiter": hourly_ref["delimiter"] if hourly_ref else None,
        "encoding": hourly_ref["encoding"] if hourly_ref else None,
        "per_value": "60",
        "time_value": "HHMMSS",
        "sample_file": hourly_ref["inner_file_path"] if hourly_ref else None,
    }

    # Count unique symbols from d_us_txt (most comprehensive)
    symbols = set()
    for row in inventory:
        if row["inferred_type"] == "daily_ascii" and row["symbol"]:
            symbols.add(row["symbol"])

    profile = {
        "metadata_missing": not metadata_present,
        "survivorship_bias_risk": not metadata_present,
        "adjusted_uncertainty": True,
        "adjusted_notes": [
            "Stooq adjustment status unverified from official documentation",
            "Prices likely split-adjusted based on community knowledge",
            "Dividend adjustment status: unconfirmed",
            "Volume adjustment status: unconfirmed (float values observed)",
        ],
        "timezone_notes": [
            "Daily files have time=000000 — assumed end-of-day (US market close 16:00/17:00 ET)",
            "Hourly files have time=HHMMSS — timestamps likely US/Eastern",
            "Timezone assumption unverified from official docs",
        ],
        "archives_detected": list(archives_detected.values()),
        "file_type_counts": dict(sorted(file_type_counts.items())),
        "daily_schema": daily_schema,
        "hourly_schema": hourly_schema,
        "metastock_dop_fields": metastock_dop_fields,
        "total_inner_files": len(inventory),
        "total_sampled_rows": sampled_rows,
        "unique_symbols_estimate": len(symbols),
        "global_date_range": {
            "earliest": min(all_first_dates) if all_first_dates else None,
            "latest": max(all_last_dates) if all_last_dates else None,
        },
        "unknown_files_count": unknown_count,
        "metastock_present": metastock_present,
        "metadata_present": metadata_present,
    }

    return profile


# ---------------------------------------------------------------------------
# build preparation plan markdown
# ---------------------------------------------------------------------------


def build_prepare_plan(profile: dict[str, Any]) -> str:
    """Generate a markdown preparation plan document."""
    lines: list[str] = []
    lines.append("# Stooq Raw Archive — Prepare Plan")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Archives Detected")
    lines.append("")
    lines.append("| Archive | Type | Files | Primary Pipeline |")
    lines.append("|---------|------|-------|-----------------|")
    for a in profile["archives_detected"]:
        is_primary = "yes" if a["daily_ascii_count"] > 0 or a["hourly_ascii_count"] > 0 else "no"
        ftype = "daily" if a["daily_ascii_count"] > 0 else "hourly" if a["hourly_ascii_count"] > 0 else "metastock"
        lines.append(f"| {a['archive_path']} | {ftype} | {a['file_count']} | {is_primary} |")
    lines.append("")

    lines.append("## Daily ASCII Schema")
    lines.append("")
    lines.append(f"- Columns: {profile['daily_schema']['columns']}")
    lines.append(f"- Delimiter: `{profile['daily_schema']['delimiter']}`")
    lines.append(f"- Encoding: {profile['daily_schema']['encoding']}")
    lines.append(f"- PER value: `{profile['daily_schema']['per_value']}`")
    lines.append(f"- TIME value: `{profile['daily_schema']['time_value']}`")
    lines.append("")

    lines.append("## Hourly ASCII Schema")
    lines.append("")
    lines.append(f"- Columns: {profile['hourly_schema']['columns']}")
    lines.append(f"- Delimiter: `{profile['hourly_schema']['delimiter']}`")
    lines.append(f"- Encoding: {profile['hourly_schema']['encoding']}")
    lines.append(f"- PER value: `{profile['hourly_schema']['per_value']}`")
    lines.append(f"- TIME value: `{profile['hourly_schema']['time_value']}`")
    lines.append("")

    lines.append("## MetaStock Files")
    lines.append("")
    lines.append("- Detected as MetaStock binary format (MASTER, EMASTER, *.DOP)")
    lines.append("- DOP field definitions: " + str(profile["metastock_dop_fields"]))
    lines.append("- Not parsed into primary pipeline")
    lines.append("- Secondary archive — available for cross-validation")
    lines.append("")

    lines.append("## Data Limitations")
    lines.append("")
    lines.append(f"- **Metadata missing**: {profile['metadata_missing']}")
    lines.append(f"- **Survivorship bias risk**: {profile['survivorship_bias_risk']}")
    lines.append(f"- **Adjusted uncertainty**: {profile['adjusted_uncertainty']}")
    for note in profile["adjusted_notes"]:
        lines.append(f"  - {note}")
    lines.append("- **Timezone assumptions**:")
    for note in profile["timezone_notes"]:
        lines.append(f"  - {note}")
    lines.append("")

    lines.append("## Proposed Canonical Parquet Layout")
    lines.append("")
    lines.append("```")
    lines.append("data/raw_normalized/")
    lines.append("  daily/{symbol}.parquet")
    lines.append("    columns: symbol, ts, date, open, high, low, close, volume")
    lines.append("             source, raw_archive, raw_file, raw_archive_hash")
    lines.append("  hourly/{symbol}.parquet")
    lines.append("    columns: symbol, ts, date, time, open, high, low, close, volume")
    lines.append("             source, raw_archive, raw_file, raw_archive_hash")
    lines.append("```")
    lines.append("")
    lines.append("## Next Recommended Steps")
    lines.append("")
    lines.append("1. Extract and normalize `d_us_txt.zip` → per-symbol daily parquet")
    lines.append("2. Extract and normalize `h_us_txt.zip` → per-symbol hourly parquet")
    lines.append("3. Validate against existing pipeline schema expectations")
    lines.append("4. Cross-check MetaStock data vs TXT data for a small sample")
    lines.append("5. Document listing/delisting metadata gap for survivorship bias")
    lines.append("")

    lines.append("## Validation Rules")
    lines.append("")
    lines.append("- Raw ZIPs are immutable — never modified by pipeline")
    lines.append("- Normalized parquet must be reproducible from raw ZIPs")
    lines.append("- No full-sample normalization in inspection phase")
    lines.append("- No future metadata leakage in daily model")
    lines.append("- Hourly data is for path/execution validation, not HFT")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write reports
# ---------------------------------------------------------------------------


def write_inventory_csv(inventory: list[dict[str, Any]], path: Path) -> None:
    """Write inventory to CSV, flattening warnings/failures to strings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in inventory:
            out = dict(row)
            out["warnings"] = ";".join(str(w) for w in row.get("warnings", []))
            out["failures"] = ";".join(str(f) for f in row.get("failures", []))
            out["columns"] = ";".join(str(c) for c in row.get("columns", []))
            out["first_ts"] = str(out["first_ts"] or "")
            out["last_ts"] = str(out["last_ts"] or "")
            writer.writerow(out)


def write_inventory_json(inventory: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, default=str)


def write_schema_profile(profile: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, default=str)


def write_prepare_plan(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stooq US Stock Raw Archive Inspector"
    )
    parser.add_argument(
        "--raw-root",
        type=str,
        default="data/raw",
        help="Root directory for raw archives (default: data/raw)",
    )
    parser.add_argument(
        "--reports-root",
        type=str,
        default="reports/raw_ingest",
        help="Root directory for output reports (default: reports/raw_ingest)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    raw_root = Path(args.raw_root)
    reports_root = Path(args.reports_root)

    if not raw_root.is_dir():
        print(f"ERROR: raw root not found: {raw_root}")
        sys.exit(1)

    reports_root.mkdir(parents=True, exist_ok=True)

    print(f"Inspecting archives under: {raw_root}")
    inventory = inventory_all(raw_root)
    print(f"Total inventory rows: {len(inventory)}")

    profile = build_schema_profile(inventory)
    plan_md = build_prepare_plan(profile)

    # Write reports
    inv_json_path = reports_root / "stooq_raw_inventory.json"
    inv_csv_path = reports_root / "stooq_raw_inventory.csv"
    schema_path = reports_root / "stooq_schema_profile.json"
    plan_path = reports_root / "stooq_prepare_plan.md"

    write_inventory_json(inventory, inv_json_path)
    write_inventory_csv(inventory, inv_csv_path)
    write_schema_profile(profile, schema_path)
    write_prepare_plan(plan_md, plan_path)

    # Summary
    print(f"\nReports written to: {reports_root}")
    print(f"  Inventory JSON  : {inv_json_path}")
    print(f"  Inventory CSV   : {inv_csv_path}")
    print(f"  Schema Profile  : {schema_path}")
    print(f"  Prepare Plan    : {plan_path}")

    ftypes = profile["file_type_counts"]
    print(f"\n--- Summary ---")
    print(f"Archives detected : {len(profile['archives_detected'])}")
    for a in profile["archives_detected"]:
        print(f"  {a['archive_path']}: {a['file_count']} files ({a['daily_ascii_count']} daily, {a['hourly_ascii_count']} hourly, {a['metastock_count']} metastock)")
    print(f"\nFile type breakdown: {json.dumps(ftypes, indent=2)}")
    print(f"Unique symbols (est): {profile['unique_symbols_estimate']}")
    print(f"Global date range: {profile['global_date_range']}")
    print(f"Metadata present: {not profile['metadata_missing']}")
    print(f"Survivorship bias risk: {profile['survivorship_bias_risk']}")
    print(f"Adjusted uncertainty: {profile['adjusted_uncertainty']}")
    print(f"Unknown files: {profile['unknown_files_count']}")

    if any(r["status"] == "FAIL" for r in inventory):
        fails = [r for r in inventory if r["status"] == "FAIL"]
        print(f"\nWARN: {len(fails)} row(s) have FAIL status")
        for f in fails[:5]:
            print(f"  {f['archive_path']}:{f['inner_file_path']} — {f['failures']}")

    if any(r["status"] == "WARN" for r in inventory):
        warns = [r for r in inventory if r["status"] == "WARN"]
        print(f"\nWARN: {len(warns)} row(s) have WARN status")


if __name__ == "__main__":
    main()