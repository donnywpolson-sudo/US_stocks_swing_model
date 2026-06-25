from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from quant_project_daily.config import ProjectPaths
from quant_project_daily.targets_vol_norm import (
    VOL_NORM60_COLUMNS,
    generate_vol_norm60_targets,
    run_vol_norm60_targets,
    vol_norm60_target_path,
)


def _labeled_frame(tickers: list[str] | None = None, rows: int = 70) -> pd.DataFrame:
    tickers = tickers or ["A", "B", "C", "D", "E"]
    dates = pd.bdate_range("2020-01-01", periods=rows)
    frames = []
    for j, ticker in enumerate(tickers):
        close = pd.Series([20.0 + j + i * 0.05 + np.sin(i / 3.0) * 0.1 for i in range(rows)])
        open_ = close - 0.05
        volume = pd.Series([1000 + j * 10 + i for i in range(rows)])
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "open": open_,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": volume,
                    "dollar_volume": close * volume,
                    "model_eligible": True,
                    "next_open": open_.shift(-1),
                    "exit_close_5d": close.shift(-5),
                    "exit_date_5d": dates.to_series().shift(-5).to_numpy(),
                    "fwd_ret_5d": close.shift(-5) / open_.shift(-1) - 1,
                    "has_split_like_gap_in_target_window_5d": False,
                    "label_valid_5d": True,
                    "target_class_5d": 0,
                    "target_long_top20_5d": False,
                    "target_short_bottom20_5d": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _paths(tmp_path: Path, labeled_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "raw_txt",
        raw_manifest=tmp_path / "raw_manifest",
        validated=tmp_path / "validated",
        normalized=tmp_path / "normalized",
        causal=tmp_path / "causal",
        research_ohlcv_daily=tmp_path / "research_ohlcv_daily",
        labeled_target_h5=labeled_path,
        feature_matrix_baseline_h5=tmp_path / "official_baseline_h5",
        feature_matrix_expanded_h5=tmp_path / "expanded_h5",
        frozen_features_expanded_h5_v1=tmp_path / "frozen",
        oos_predictions_baseline_h5=tmp_path / "official_oos_baseline_h5",
        validation_reports=tmp_path / "reports" / "validation",
        label_reports=tmp_path / "reports" / "labels",
        feature_reports=tmp_path / "reports" / "features",
        wfa_reports=tmp_path / "reports" / "wfa",
        metrics_reports=tmp_path / "reports" / "metrics",
        gates_reports=tmp_path / "reports" / "gates",
    )


def test_vol_norm60_columns_are_trailing_only_for_earlier_dates() -> None:
    base = _labeled_frame(rows=90)
    changed = base.copy()
    cutoff = pd.Timestamp("2020-04-15")
    changed.loc[(changed["ticker"] == "A") & (changed["date"] >= cutoff), ["close", "high", "low"]] = [
        9999.0,
        10000.0,
        9998.0,
    ]

    base_out = generate_vol_norm60_targets(base).data.sort_values(["ticker", "date"]).reset_index(drop=True)
    changed_out = generate_vol_norm60_targets(changed).data.sort_values(["ticker", "date"]).reset_index(drop=True)

    early = (base_out["ticker"] == "A") & (pd.to_datetime(base_out["date"]) < cutoff)
    for col in VOL_NORM60_COLUMNS:
        pd.testing.assert_series_equal(
            base_out.loc[early, col].reset_index(drop=True),
            changed_out.loc[early, col].reset_index(drop=True),
            check_names=False,
        )


def test_vol_norm60_denominator_is_ticker_local() -> None:
    base = _labeled_frame(rows=90)
    changed = base.copy()
    changed.loc[changed["ticker"] == "A", ["close", "high", "low"]] = [9999.0, 10000.0, 9998.0]

    base_out = generate_vol_norm60_targets(base).data.sort_values(["ticker", "date"]).reset_index(drop=True)
    changed_out = generate_vol_norm60_targets(changed).data.sort_values(["ticker", "date"]).reset_index(drop=True)

    b_rows = base_out["ticker"] == "B"
    pd.testing.assert_series_equal(
        base_out.loc[b_rows, "fwd_ret_5d_vol_norm60"].reset_index(drop=True),
        changed_out.loc[b_rows, "fwd_ret_5d_vol_norm60"].reset_index(drop=True),
        check_names=False,
    )


def test_vol_norm60_invalid_or_zero_volatility_rows_are_not_label_valid() -> None:
    labeled = _labeled_frame(tickers=["A"], rows=70)
    labeled["close"] = 10.0
    labeled["fwd_ret_5d"] = 0.01

    out = generate_vol_norm60_targets(labeled).data

    assert out["label_valid_5d_vol_norm60"].sum() == 0
    assert out["fwd_ret_5d_vol_norm60"].isna().all()


def test_vol_norm60_classes_use_per_date_top_bottom_20pct() -> None:
    labeled = _labeled_frame(rows=70)
    target_date = pd.Timestamp("2020-03-25")
    returns = {"A": -0.5, "B": -0.1, "C": 0.0, "D": 0.2, "E": 0.8}
    for ticker, ret in returns.items():
        labeled.loc[(labeled["ticker"] == ticker) & (labeled["date"] == target_date), "fwd_ret_5d"] = ret

    out = generate_vol_norm60_targets(labeled).data
    first_date = out.loc[pd.to_datetime(out["date"]) == target_date, ["ticker", "target_class_5d_vol_norm60"]]
    got = dict(zip(first_date["ticker"], first_date["target_class_5d_vol_norm60"]))

    assert got["A"] == -1
    assert got["E"] == 1
    assert got["B"] == 0
    assert got["C"] == 0
    assert got["D"] == 0


def test_vol_norm60_target_run_writes_experimental_path_only(tmp_path: Path) -> None:
    active_path = tmp_path / "data" / "labeled" / "target_h5"
    active_path.mkdir(parents=True)
    _labeled_frame(rows=90).to_parquet(active_path / "targets.parquet", index=False)
    paths = _paths(tmp_path, active_path)

    with patch("quant_project_daily.targets_vol_norm.reset_parquet_output_dir") as mock_reset:
        mock_reset.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)
        summary = run_vol_norm60_targets(paths=paths)

    assert summary["official_target_replaced"] is False
    assert (vol_norm60_target_path(paths) / "targets.parquet").exists()
    assert (paths.label_reports / "target_h5_vol_norm60_experimental_summary.json").exists()
    assert (active_path / "targets.parquet").exists()
    assert not paths.feature_matrix_baseline_h5.exists()
    assert not paths.oos_predictions_baseline_h5.exists()
