from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.project_config import REPO_ROOT


BASE_URL = "https://www.alphavantage.co/query"
SOURCE_NAME = "Alpha Vantage LISTING_STATUS"
SOURCE_DOC_URL = "https://www.alphavantage.co/documentation/#listing-status"
RAW_COLUMNS = ("symbol", "name", "exchange", "assetType", "ipoDate", "delistingDate", "status")
OUTPUT_COLUMNS = (*RAW_COLUMNS, "query_state", "source", "source_asof_date")
ALLOWED_STATES = ("active", "delisted")
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "reference" / "alpha_vantage_listing_status.csv"


def _validate_state(state: str) -> str:
    value = state.strip().lower()
    if value not in ALLOWED_STATES:
        raise ValueError(f"unsupported Alpha Vantage listing state: {state}")
    return value


def _validate_date(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    text = value.strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD: {value}") from exc
    return text


def build_listing_status_url(api_key: str, *, state: str, query_date: str | None = None) -> str:
    key = api_key.strip()
    if not key:
        raise ValueError("Alpha Vantage API key is required")
    params = {
        "function": "LISTING_STATUS",
        "state": _validate_state(state),
        "apikey": key,
    }
    date_value = _validate_date(query_date, field_name="query_date")
    if date_value:
        params["date"] = date_value
    return f"{BASE_URL}?{urlencode(params)}"


def parse_listing_status_csv(
    csv_text: str,
    *,
    query_state: str,
    source_asof_date: str,
    source: str = SOURCE_NAME,
) -> list[dict[str, str]]:
    state = _validate_state(query_state)
    asof = _validate_date(source_asof_date, field_name="source_asof_date")
    reader = csv.DictReader(StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    missing = [col for col in RAW_COLUMNS if col not in fieldnames]
    if missing:
        raise ValueError(f"Alpha Vantage listing-status CSV missing columns: {', '.join(missing)}")
    rows = []
    for source_row in reader:
        if not any((source_row.get(col) or "").strip() for col in RAW_COLUMNS):
            continue
        row = {col: (source_row.get(col) or "").strip() for col in RAW_COLUMNS}
        row["query_state"] = state
        row["source"] = source
        row["source_asof_date"] = asof or ""
        rows.append(row)
    return rows


def write_listing_status_csv(rows: Iterable[dict[str, str]], output_path: Path = DEFAULT_OUTPUT_PATH) -> dict[str, str | int]:
    materialized = list(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in materialized:
            writer.writerow({col: row.get(col, "") for col in OUTPUT_COLUMNS})
    return {
        "path": str(output_path),
        "row_count": len(materialized),
        "source": SOURCE_NAME,
        "source_doc_url": SOURCE_DOC_URL,
    }


def fetch_listing_status_csv(api_key: str, *, state: str, query_date: str | None = None, timeout_seconds: int = 60) -> str:
    url = build_listing_status_url(api_key, state=state, query_date=query_date)
    request = Request(url, headers={"User-Agent": "us-stocks-swing-model-alpha-vantage-listing-status"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8-sig")


def download_alpha_vantage_listing_status(
    api_key: str,
    *,
    states: Iterable[str] = ALLOWED_STATES,
    query_date: str | None = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    source_asof_date: str | None = None,
    pause_seconds: float = 15.0,
) -> dict[str, str | int]:
    asof = source_asof_date or datetime.now(timezone.utc).date().isoformat()
    rows: list[dict[str, str]] = []
    normalized_states = [_validate_state(state) for state in states]
    for index, state in enumerate(normalized_states):
        if index and pause_seconds > 0:
            time.sleep(pause_seconds)
        rows.extend(parse_listing_status_csv(fetch_listing_status_csv(api_key, state=state, query_date=query_date), query_state=state, source_asof_date=asof))
    return write_listing_status_csv(rows, output_path)
