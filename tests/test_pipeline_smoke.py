"""Synthetic end-to-end smoke test for daily pipeline stage handoffs."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_project_daily.normalize_daily import normalize_daily
from quant_project_daily.causal_gating import apply_causal_gating
from quant_project_daily.research_universe import build_research_universe
from quant_project_daily.targets import generate_targets
from quant_project_daily.features_baseline import build_baseline_features
from quant_project_daily.wfa_splits import build_wfa_plan
from quant_project_daily.baseline_wfa import run_fold
from quant_project_daily.metrics import build_metrics

# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------

TICKERS = [f"TK{i:02d}" for i in range(1, 11)]  # 10 tickers
N_DAYS = 900  # business days — covers 2007-01-01 to ~2010-08


def _make_synthetic_ohlcv() -> pd.DataFrame:
    """Build a deterministic OHLCV universe in long format."""
    dates = pd.bdate_range("2007-01-01", periods=N_DAYS, freq="B")
    rows: list[dict] = []
    rng = np.random.default_rng(42)
    for t_idx, ticker in enumerate(TICKERS):
        base_price = 10.0 + t_idx * 5
        log_returns = rng.normal(0.0002, 0.015, size=N_DAYS)
        close = base_price * np.exp(np.cumsum(log_returns))
        high = close * (1.0 + rng.uniform(0.001, 0.03, size=N_DAYS))
        low = close * (1.0 - rng.uniform(0.001, 0.03, size=N_DAYS))
        open_ = low + (high - low) * rng.uniform(0.2, 0.8, size=N_DAYS)
        volume = rng.integers(50_000, 500_000, size=N_DAYS).astype(float)
        for i, d in enumerate(dates):
            rows.append(
                {
                    "date": d,
                    "raw_ticker": ticker,
                    "ticker": ticker,
                    "open": float(open_[i]),
                    "high": float(high[i]),
                    "low": float(low[i]),
                    "close": float(close[i]),
                    "volume": float(volume[i]),
                    "openint": 0.0,
                    "source_file": "synthetic",
                    "year": int(d.year),
                }
            )
    return pd.DataFrame(rows)


def _feature_cfg() -> dict:
    """Return the minimal feature-column config expected by build_baseline_features."""
    return {
        "feature_columns": [
            "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d", "ret_60d",
            "gap_return", "intraday_return",
            "realized_vol_5d", "realized_vol_10d", "realized_vol_20d", "realized_vol_60d",
            "true_range_pct", "atr_14_pct", "range_pct", "range_z_20d",
            "body_pct", "upper_wick_pct", "lower_wick_pct", "close_position_in_day_range",
            "dist_sma_10d", "dist_sma_20d", "dist_sma_50d", "dist_sma_200d",
            "sma_20d_slope", "sma_50d_slope", "sma_200d_slope",
            "dist_to_20d_high", "dist_to_60d_high", "dist_to_252d_high",
            "dist_to_20d_low", "dist_to_60d_low", "dist_to_252d_low",
            "drawdown_from_60d_high", "drawdown_from_252d_high",
            "bounce_from_20d_low", "bounce_from_60d_low",
            "rsi_14", "rsi_30",
            "close_position_in_20d_range", "close_position_in_60d_range",
            "volume_z_20d", "volume_z_60d",
            "dollar_volume_z_20d", "dollar_volume_z_60d",
            "volume_ratio_5d_20d", "dollar_volume_ratio_5d_20d",
            "day_of_week", "month",
            "rank_ret_20d", "rank_rsi_14", "rank_drawdown_from_60d_high",
            "rank_dist_to_60d_low", "rank_volume_z_20d", "rank_dollar_volume_z_20d",
        ],
        "target_columns": [
            "fwd_ret_20d", "label_valid_20d", "target_class_20d",
            "target_long_top20_20d", "target_short_bottom20_20d",
        ],
        "metadata_columns": [
            "date", "ticker", "raw_ticker", "open", "high", "low",
            "close", "volume", "dollar_volume", "model_eligible", "year",
        ],
        "excluded_columns": [
            "next_open", "exit_close_20d", "exit_date_20d",
            "has_split_like_gap_in_target_window_20d",
        ],
    }


# ---------------------------------------------------------------------------
# Main smoke test
# ---------------------------------------------------------------------------

def test_synthetic_daily_pipeline_smoke() -> None:
    """Verify every stage handoff produces non-empty, coherent artifacts."""

    # ---- 0. synthetic universe ----
    raw = _make_synthetic_ohlcv()
    assert len(raw) == len(TICKERS) * N_DAYS

    # ---- 1. normalize_daily ----
    normalized = normalize_daily(raw)
    assert not normalized.empty, "normalize_daily returned empty"
    assert "dollar_volume" in normalized.columns, "missing dollar_volume"

    # ---- 2. apply_causal_gating ----
    gated = apply_causal_gating(
        normalized,
        min_history_bars=5,
        price_min=1.0,
        median_dollar_volume_lookback=3,
        median_dollar_volume_min=0.0,
        zero_volume_lookback=3,
    )

    assert not gated.empty
    assert gated["tradable"].any(), "synthetic causal gating produced no tradable rows"


    # ---- 3. build_research_universe ----
    ru = build_research_universe(
        gated,
        warmup_start_date="2008-01-01",
        research_start_date="2010-01-01",
    )
    assert not ru.data.empty, "research universe empty"
    assert ru.data["model_eligible"].any(), "no model_eligible rows"

    # ---- 4. generate_targets ----
    tg = generate_targets(
        ru.data,
        split_gaps=pd.DataFrame(columns=["ticker", "date"]),
        research_start_date="2010-01-01",
        horizon_days=20,
        top_bottom_quantile=0.20,
        excluded_tickers=[],
    )
    assert not tg.data.empty, "targets output empty"
    assert tg.data["label_valid_20d"].any(), "no label_valid_20d rows"

    # ---- 5. build_baseline_features ----
    feature_result = build_baseline_features(tg.data, cfg=_feature_cfg())
    assert not feature_result.data.empty, "feature output empty"
    assert feature_result.registry.get("feature_cols"), "registry feature_cols empty"

    # ---- 6. build_wfa_plan ----
    date_counts = (
        feature_result.data.groupby("date")
        .size()
        .reset_index(name="row_count")
    )
    date_count = len(date_counts)
    assert date_count >= 12, f"not enough feature dates for smoke WFA: {date_count}"

    test_days = min(5, max(1, date_count // 6))
    purge_days = min(5, max(1, date_count // 6))
    train_days = min(20, max(5, date_count - purge_days - test_days))
    step_days = test_days

    assert train_days + purge_days + test_days <= date_count

    wfa = build_wfa_plan(
        date_counts,
        {
            "train_window_days": train_days,
            "test_window_days": test_days,
            "step_days": step_days,
            "purge_days": purge_days,
            "embargo_days": 0,
        },
    )

    assert len(wfa.plan) >= 1, "WFA plan has no folds"
    first_fold = wfa.plan.iloc[0]
    assert first_fold["train_end_date"] < first_fold["test_start_date"]
    assert first_fold["purge_end_date"] < first_fold["test_start_date"]

    # ---- 7. run_fold (single fold) ----
    first_fold = wfa.plan.iloc[0]
    model_cfg = {"target_column": "target_class_20d", "ridge_alpha": 1.0}
    fold_result = run_fold(feature_result.data, first_fold, feature_result.registry["feature_cols"], model_cfg)
    assert not fold_result.predictions.empty, "fold predictions empty"
    for col in ("pred_score_20d", "pred_rank_pct_by_date", "fold_id"):
        assert col in fold_result.predictions.columns, f"missing column {col}"

    # ---- 8. build_metrics ----
    metrics_cfg = {
        "round_trip_cost_bps": 25,
        "decile_buckets": 5,
        "quintile_buckets": 5,
        "score_outlier_abs_threshold": 5.0,
    }
    summary, _reports = build_metrics(fold_result.predictions, metrics_cfg)
    assert summary["total_oos_rows"] > 0, "no OOS rows in metrics"
    assert "missing_oos_predictions" not in summary.get("blockers", []), (
        "metrics blocked by missing_oos_predictions"
    )