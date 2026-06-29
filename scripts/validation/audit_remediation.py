from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from scripts.project_config import ProjectPaths, project_paths
from scripts.execution import assign_score_buckets
from scripts.phase8_model_selection.metrics import build_metrics, load_execution_costs, read_oos_predictions


NEGATIVE_CONTROL_SEEDS = (17, 29)
FIXED_TOP_N = 25
HASH_MAX_BYTES = 25_000_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, default=str), encoding="utf-8")


def _format_metric(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.8f}"
    return str(value)


def _prepare_predictions(preds: pd.DataFrame) -> pd.DataFrame:
    required = {"fold_id", "date", "ticker", "fwd_ret_5d", "pred_score_5d"}
    missing = sorted(required - set(preds.columns))
    if missing:
        raise ValueError(f"missing required OOS prediction columns: {missing}")

    df = preds.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values(["date", "ticker", "fold_id"], kind="mergesort").reset_index(drop=True)


def _control_frames(preds: pd.DataFrame, seeds: Iterable[int]) -> Iterable[tuple[str, int | None, pd.DataFrame]]:
    base = _prepare_predictions(preds)
    yield "active_model", None, base

    for seed in seeds:
        control = base.copy()
        control["pred_score_5d"] = np.nan
        for date_index, (_, group_index) in enumerate(control.groupby("date", sort=True).groups.items()):
            date_rng = np.random.default_rng((seed * 1_000_003) + date_index)
            control.loc[group_index, "pred_score_5d"] = date_rng.standard_normal(len(group_index))
        yield f"random_score_seed_{seed}", seed, control

    null_control = base.copy()
    null_control["pred_score_5d"] = 0.0
    yield "null_constant_score", None, null_control

    lagged = base.sort_values(["ticker", "date", "fold_id"], kind="mergesort").copy()
    lagged["pred_score_5d"] = lagged.groupby("ticker", sort=False)["pred_score_5d"].shift(1)
    lagged = lagged.sort_values(["date", "ticker", "fold_id"], kind="mergesort").reset_index(drop=True)
    yield "lagged_score_by_ticker", None, lagged


def _fixed_top_n_turnover(selected: pd.DataFrame) -> float | None:
    if selected.empty:
        return None
    previous: set[str] | None = None
    turnovers: list[float] = []
    for _, tickers in selected.groupby("date", sort=True)["ticker"]:
        current = {str(t) for t in tickers}
        if previous is not None and current:
            turnovers.append(len(current - previous) / len(current))
        previous = current
    return float(np.mean(turnovers)) if turnovers else None


def _fixed_top_n_metrics(preds: pd.DataFrame, cfg: dict[str, Any], top_n: int) -> dict[str, Any]:
    df = preds.dropna(subset=["pred_score_5d", "fwd_ret_5d"]).copy()
    if df.empty:
        return {
            "fixed_top_n": int(top_n),
            "fixed_top_n_active_days": 0,
            "fixed_top_n_avg_names": None,
            "fixed_top_n_gross_return": None,
            "fixed_top_n_net_return": None,
            "fixed_top_n_one_way_turnover": None,
        }

    cost = float(cfg["round_trip_cost_bps"]) / 10_000.0
    df["fixed_top_n_rank"] = df.groupby("date", sort=False)["pred_score_5d"].rank(method="first", ascending=False)
    selected = df.loc[df["fixed_top_n_rank"] <= top_n].copy()
    daily = (
        selected.groupby("date", sort=True)
        .agg(selected_count=("ticker", "size"), gross_return=("fwd_ret_5d", "mean"))
        .reset_index()
    )
    daily["net_return"] = daily["gross_return"] - cost
    return {
        "fixed_top_n": int(top_n),
        "fixed_top_n_active_days": int(len(daily)),
        "fixed_top_n_avg_names": float(daily["selected_count"].mean()) if not daily.empty else None,
        "fixed_top_n_gross_return": float(daily["gross_return"].mean()) if not daily.empty else None,
        "fixed_top_n_net_return": float(daily["net_return"].mean()) if not daily.empty else None,
        "fixed_top_n_one_way_turnover": _fixed_top_n_turnover(selected),
    }


def _top_decile_turnover(preds: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    df = preds.dropna(subset=["pred_score_5d", "fwd_ret_5d"]).copy()
    if df.empty:
        return {"top_decile_avg_names": None, "top_decile_one_way_turnover": None}

    deciles = int(cfg.get("decile_buckets", 10))
    df["decile"] = assign_score_buckets(df, deciles)
    selected = df.loc[df["decile"] == deciles]
    names_by_date = selected.groupby("date", sort=True).size()
    return {
        "top_decile_avg_names": float(names_by_date.mean()) if not names_by_date.empty else None,
        "top_decile_one_way_turnover": _fixed_top_n_turnover(selected),
    }


def build_negative_control_diagnostics(
    preds: pd.DataFrame,
    cfg: dict[str, Any],
    seeds: Iterable[int] = NEGATIVE_CONTROL_SEEDS,
    top_n: int = FIXED_TOP_N,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    if preds.empty:
        summary = {
            "diagnostic_name": "baseline_h5_negative_controls",
            "blockers": ["missing_oos_predictions"],
            "warnings": [],
            "input_oos_rows": 0,
            "controls": [],
            "notes": [
                "Diagnostic artifact only; does not alter h5 labels, features, WFA splits, metrics gates, or gate status.",
            ],
        }
        return summary, pd.DataFrame(), pd.DataFrame()

    rows: list[dict[str, Any]] = []
    folds: list[pd.DataFrame] = []
    seed_values = tuple(int(s) for s in seeds)

    for control_name, seed, control_df in _control_frames(preds, seed_values):
        input_rows = int(len(control_df))
        metrics_summary, reports = build_metrics(control_df, cfg)
        fixed_metrics = _fixed_top_n_metrics(control_df, cfg, top_n)
        row = {
            "control_name": control_name,
            "seed": seed,
            "input_rows": input_rows,
            "rows_used": metrics_summary.get("total_oos_rows"),
            "dropped_rows": input_rows - int(metrics_summary.get("total_oos_rows", 0) or 0),
            "fold_count": metrics_summary.get("fold_count"),
            "mean_daily_rank_ic": metrics_summary.get("mean_daily_rank_ic"),
            "rank_ic_t_stat": metrics_summary.get("rank_ic_t_stat"),
            "top_decile_gross_return": metrics_summary.get("top_decile_gross_return"),
            "top_decile_net_return": metrics_summary.get("top_decile_net_return"),
            "long_short_gross_return": metrics_summary.get("long_short_gross_return"),
            "long_short_net_return": metrics_summary.get("long_short_net_return"),
            "round_trip_cost_bps": metrics_summary.get("round_trip_cost_bps"),
            "warnings": ";".join(metrics_summary.get("warnings", [])),
            "blockers": ";".join(metrics_summary.get("blockers", [])),
        }
        row.update(fixed_metrics)
        row.update(_top_decile_turnover(control_df, cfg))
        rows.append(row)

        fold_metrics = reports.get("fold_metrics")
        if fold_metrics is not None and not fold_metrics.empty:
            fold_copy = fold_metrics.copy()
            fold_copy.insert(0, "control_name", control_name)
            fold_copy.insert(1, "seed", seed)
            folds.append(fold_copy)

    by_control = pd.DataFrame(rows)
    by_fold = pd.concat(folds, ignore_index=True) if folds else pd.DataFrame()
    summary = {
        "diagnostic_name": "baseline_h5_negative_controls",
        "model_name": "baseline_h5",
        "input_oos_rows": int(len(preds)),
        "random_seeds": list(seed_values),
        "fixed_top_n": int(top_n),
        "controls": by_control["control_name"].tolist(),
        "control_count": int(len(by_control)),
        "blockers": [],
        "warnings": [],
        "notes": [
            "Diagnostic artifact only; does not alter h5 labels, features, WFA splits, metrics gates, or gate status.",
            "Random-score controls are generated per date from fixed seeds after deterministic date/ticker/fold sorting.",
            "Null and lagged-score controls are sanity checks, not investable signals or trading instructions.",
        ],
    }
    return summary, by_control, by_fold


def build_negative_controls_markdown(
    summary: dict[str, Any],
    by_control: pd.DataFrame,
    input_path: Path,
    generated_at_utc: str,
) -> str:
    lines = [
        "# baseline_h5 Negative-Control Diagnostic",
        "",
        f"Generated UTC: {generated_at_utc}",
        f"Input predictions: `{input_path.as_posix()}`",
        "",
        "This is a research diagnostic. It does not change h5 labels, feature engineering, WFA splits, model training, metrics gates, or the official gate status.",
        "",
        "## Controls",
        "",
        "- `active_model`: existing `pred_score_5d` from baseline_h5 OOS predictions.",
        "- `random_score_seed_17` and `random_score_seed_29`: per-date Gaussian random scores from fixed seeds after deterministic sorting.",
        "- `null_constant_score`: constant zero score sanity check.",
        "- `lagged_score_by_ticker`: prior available OOS score within each ticker, with first ticker rows dropped by metric construction.",
        "",
        "## Summary",
        "",
    ]
    if by_control.empty:
        lines.append("* No controls were computed because OOS predictions were unavailable.")
    else:
        columns = [
            "control_name",
            "seed",
            "rows_used",
            "mean_daily_rank_ic",
            "rank_ic_t_stat",
            "top_decile_net_return",
            "top_decile_one_way_turnover",
            "long_short_net_return",
            "fixed_top_n_net_return",
            "fixed_top_n_one_way_turnover",
        ]
        lines.append("| control | seed | rows used | mean rank IC | rank IC t | top decile net | top decile turnover | long/short net | fixed top-N net | fixed top-N turnover |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, row in by_control[columns].iterrows():
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["control_name"]),
                        _format_metric(row["seed"]),
                        _format_metric(row["rows_used"]),
                        _format_metric(row["mean_daily_rank_ic"]),
                        _format_metric(row["rank_ic_t_stat"]),
                        _format_metric(row["top_decile_net_return"]),
                        _format_metric(row["top_decile_one_way_turnover"]),
                        _format_metric(row["long_short_net_return"]),
                        _format_metric(row["fixed_top_n_net_return"]),
                        _format_metric(row["fixed_top_n_one_way_turnover"]),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- Passing or failing this diagnostic is not a trade recommendation and is not a profitability claim.",
            "- Results remain research-ready and walk-forward-ready evidence only.",
            "- The official `baseline_h5_research_gate` remains controlled by the existing gate report and thresholds.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_data_universe_limitations_markdown(paths: ProjectPaths, generated_at_utc: str) -> str:
    evidence_paths = [
        paths.raw_txt,
        paths.raw_manifest,
        paths.validated,
        paths.normalized,
        paths.causal,
        paths.research_ohlcv_daily,
        paths.labeled_target_h5,
        paths.feature_matrix_baseline_h5,
        paths.oos_predictions_baseline_h5,
    ]
    lines = [
        "# baseline_h5 Data And Universe Limitations",
        "",
        f"Generated UTC: {generated_at_utc}",
        "",
        "This audit note documents known evidence gaps for the h5 / 5d daily OHLCV research pipeline. It is a research-ready and walk-forward-ready limitation report, not investment advice, a profitability claim, or live-trading readiness evidence.",
        "",
        "## Scope",
        "",
        "- Active target: h5 / 5 trading days.",
        "- Label timing: enter at `next_open` and exit at `exit_close_5d`; `fwd_ret_5d = exit_close_5d / next_open - 1`.",
        "- Available raw schema: `<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>`.",
        "- Daily bars are expected to use `PER=D` and `TIME=000000`.",
        "",
        "## Evidence Gaps",
        "",
        "- No point-in-time security master is present in the audited artifacts, so common-stock-only, ETF/ETN exclusion, warrants/units/rights/preferreds exclusion, ADR exclusion, exchange filter, and OTC exclusion are not proven.",
        "- Survivorship coverage and delisted-name inclusion are not proven from the available OHLCV-only artifacts.",
        "- Permanent security identifiers are not present, so ticker changes, mergers, and issuer identity continuity remain unresolved.",
        "- Corporate-action adjustment, dividend, and distribution treatment is not independently proven by the audited files.",
        "- Borrow availability, locate availability, shortability, option liquidity, and option P&L are outside the evidenced dataset.",
        "- Execution modeling remains limited to configured flat round-trip bps costs unless a separate audited cost model proves otherwise.",
        "- Timezone, exchange calendar, holiday, half-day, and halt/session assumptions are not independently proven beyond daily date bars in the audited artifacts.",
        "",
        "## Research Implication",
        "",
        "The current artifacts can support OHLCV-only research filters such as price, volume, dollar-volume, history length, zero-volume, and traded-days checks. They do not prove a fully point-in-time investable universe or live execution environment. Results should therefore remain described only as research-ready and walk-forward-ready.",
        "",
        "## Evidence Paths",
        "",
    ]
    for path in evidence_paths:
        lines.append(f"- `{_rel(path, paths.repo_root)}`")
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
            "- Do not claim production readiness, live-trading readiness, investment advice, or expected profitability from these artifacts.",
            "- Do not treat unavailable metadata filters as implemented unless future files/configs prove them.",
            "- Preserve the official h5 gate result until the existing gate report is regenerated by the established stage.",
        ]
    )
    return "\n".join(lines) + "\n"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_record(path: Path, root: Path, hash_max_bytes: int = HASH_MAX_BYTES) -> dict[str, Any]:
    record: dict[str, Any] = {"path": _rel(path, root), "exists": path.exists()}
    if not path.exists():
        return record
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        record.update(
            {
                "kind": "directory",
                "file_count": len(files),
                "total_bytes": int(sum(p.stat().st_size for p in files)),
                "parquet_count": int(sum(1 for p in files if p.suffix == ".parquet")),
                "csv_count": int(sum(1 for p in files if p.suffix == ".csv")),
                "json_count": int(sum(1 for p in files if p.suffix == ".json")),
                "latest_mtime_utc": max((datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds") for p in files), default=None),
            }
        )
        return record

    stat = path.stat()
    record.update(
        {
            "kind": "file",
            "bytes": int(stat.st_size),
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        }
    )
    if stat.st_size <= hash_max_bytes:
        record["sha256"] = _sha256_file(path)
    else:
        record["sha256"] = None
        record["hash_skipped_reason"] = f"file exceeds {hash_max_bytes} byte hash limit"
    return record


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False, timeout=15)
    except Exception as exc:  # pragma: no cover - defensive for non-git temp dirs
        return f"unavailable: {exc}"
    output = (result.stdout or result.stderr).strip()
    return output if output else ""


def build_provenance_manifest(
    paths: ProjectPaths,
    preds: pd.DataFrame,
    generated_at_utc: str,
    command: str = "python scripts/audit_baseline_h5_remediation.py",
) -> dict[str, Any]:
    root = paths.repo_root
    config_paths = [
        root / "configs" / "project.yaml",
        root / "configs" / "execution_costs.yaml",
        root / "configs" / "gates.yaml",
        root / "configs" / "baseline_model.yaml",
        root / "configs" / "baseline_features.yaml",
        root / "configs" / "wfa.yaml",
    ]
    gate_inputs = [
        paths.oos_predictions_baseline_h5,
        paths.metrics_reports / "baseline_h5_metrics_summary.json",
        paths.gates_reports / "baseline_h5_gate.json",
        paths.wfa_reports / "baseline_h5_split_summary.json",
        paths.wfa_reports / "baseline_h5_oos_summary.json",
        paths.label_reports / "target_h5_summary.json",
        paths.feature_reports / "baseline_h5_summary.json",
    ]
    return {
        "manifest_name": "baseline_h5_gate_provenance_manifest",
        "generated_at_utc": generated_at_utc,
        "command": command,
        "repo_root": str(root),
        "git": {
            "commit": _git(["rev-parse", "HEAD"], root),
            "branch": _git(["branch", "--show-current"], root),
            "worktree_status_short": _git(["status", "--short"], root),
        },
        "config_artifacts": [_path_record(path, root) for path in config_paths],
        "gate_consumed_artifacts": [_path_record(path, root) for path in gate_inputs],
        "oos_prediction_rows_observed": int(len(preds)),
        "oos_prediction_columns_observed": sorted(preds.columns.tolist()) if not preds.empty else [],
        "research_guardrails": [
            "Manifest is provenance evidence only; it does not alter gates or metrics.",
            "Artifacts remain research-ready and walk-forward-ready only.",
            "No investment advice, profitability claim, production readiness, or live-trading readiness is implied.",
        ],
    }


def build_provenance_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# baseline_h5 Gate Provenance Manifest",
        "",
        f"Generated UTC: {manifest['generated_at_utc']}",
        f"Command: `{manifest['command']}`",
        f"Git commit: `{manifest['git']['commit']}`",
        f"Git branch: `{manifest['git']['branch']}`",
        "",
        "This manifest records provenance for gate-consumed baseline_h5 artifacts. It is evidence only and does not change the official gate status.",
        "",
        "## Config Artifacts",
        "",
    ]
    for item in manifest["config_artifacts"]:
        status = "exists" if item["exists"] else "missing"
        digest = item.get("sha256") or item.get("hash_skipped_reason") or ""
        lines.append(f"- `{item['path']}`: {status} {digest}".rstrip())
    lines.extend(["", "## Gate-Consumed Artifacts", ""])
    for item in manifest["gate_consumed_artifacts"]:
        status = "exists" if item["exists"] else "missing"
        if item.get("kind") == "directory":
            detail = f"{item.get('file_count', 0)} files, {item.get('parquet_count', 0)} parquet files"
        else:
            detail = item.get("sha256") or item.get("hash_skipped_reason") or ""
        lines.append(f"- `{item['path']}`: {status} {detail}".rstrip())
    lines.extend(
        [
            "",
            "## Observed OOS Predictions",
            "",
            f"- Rows: {manifest['oos_prediction_rows_observed']}",
            f"- Columns: {', '.join(manifest['oos_prediction_columns_observed']) if manifest['oos_prediction_columns_observed'] else 'none'}",
            "",
            "## Research Guardrails",
            "",
        ]
    )
    lines.extend(f"- {guardrail}" for guardrail in manifest["research_guardrails"])
    return "\n".join(lines) + "\n"


def run_audit_remediation(
    paths: ProjectPaths | None = None,
    execution_costs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = paths or project_paths()
    generated_at_utc = _utc_now()
    cfg = execution_costs or load_execution_costs()
    preds = read_oos_predictions(p.oos_predictions_baseline_h5)
    audit_reports = p.repo_root / "reports" / "audit"

    summary, by_control, by_fold = build_negative_control_diagnostics(preds, cfg)
    p.metrics_reports.mkdir(parents=True, exist_ok=True)
    by_control.to_csv(p.metrics_reports / "baseline_h5_negative_controls_by_control.csv", index=False)
    by_fold.to_csv(p.metrics_reports / "baseline_h5_negative_controls_by_fold.csv", index=False)
    _write_json(p.metrics_reports / "baseline_h5_negative_controls_summary.json", summary)
    (p.metrics_reports / "baseline_h5_negative_controls_diagnostic.md").write_text(
        build_negative_controls_markdown(summary, by_control, p.oos_predictions_baseline_h5, generated_at_utc),
        encoding="utf-8",
    )

    audit_reports.mkdir(parents=True, exist_ok=True)
    limitations_path = audit_reports / "baseline_h5_data_universe_limitations.md"
    limitations_path.write_text(build_data_universe_limitations_markdown(p, generated_at_utc), encoding="utf-8")

    manifest = build_provenance_manifest(p, preds, generated_at_utc)
    manifest_path = audit_reports / "baseline_h5_gate_provenance_manifest.json"
    _write_json(manifest_path, manifest)
    (audit_reports / "baseline_h5_gate_provenance_manifest.md").write_text(
        build_provenance_markdown(manifest),
        encoding="utf-8",
    )

    return {
        "artifacts": {
            "limitations_report": str(limitations_path),
            "negative_controls_summary": str(p.metrics_reports / "baseline_h5_negative_controls_summary.json"),
            "negative_controls_by_control": str(p.metrics_reports / "baseline_h5_negative_controls_by_control.csv"),
            "negative_controls_by_fold": str(p.metrics_reports / "baseline_h5_negative_controls_by_fold.csv"),
            "negative_controls_markdown": str(p.metrics_reports / "baseline_h5_negative_controls_diagnostic.md"),
            "provenance_manifest": str(manifest_path),
            "provenance_markdown": str(audit_reports / "baseline_h5_gate_provenance_manifest.md"),
        },
        "negative_controls": summary,
        "provenance": {
            "commit": manifest["git"]["commit"],
            "worktree_status_short": manifest["git"]["worktree_status_short"],
            "oos_prediction_rows_observed": manifest["oos_prediction_rows_observed"],
        },
    }
