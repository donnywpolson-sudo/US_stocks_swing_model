import pandas as pd

from quant_project_daily.config import ProjectPaths
from quant_project_daily.features_baseline import build_baseline_features
from quant_project_daily.features_expanded import _run_polars, build_expanded_features, load_expanded_feature_config


def _labeled(tickers=("A", "B"), rows=300) -> pd.DataFrame:
    frames = []
    dates = pd.bdate_range("2010-01-01", periods=rows)
    for j, ticker in enumerate(tickers):
        base = 10 + j * 1000
        close = pd.Series(range(base, base + rows), dtype=float)
        open_ = close - 0.5
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "open": open_,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000 + pd.Series(range(rows)) + j,
                    "dollar_volume": close * (1000 + pd.Series(range(rows)) + j),
                    "model_eligible": True,
                    "next_open": open_.shift(-1),
                    "exit_close_20d": close.shift(-20),
                    "exit_date_20d": dates.to_series().shift(-20).to_numpy(),
                    "fwd_ret_20d": close.shift(-20) / open_.shift(-1) - 1,
                    "has_split_like_gap_in_target_window_20d": False,
                    "label_valid_20d": True,
                    "target_class_20d": 0,
                    "target_long_top20_20d": False,
                    "target_short_bottom20_20d": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _baseline_matrix(rows=300) -> pd.DataFrame:
    return build_baseline_features(_labeled(rows=rows)).data


def test_expanded_retains_baseline_and_adds_new_features_no_leakage() -> None:
    result = build_expanded_features(_baseline_matrix())
    cfg = load_expanded_feature_config()
    assert set(cfg["baseline_feature_columns"]).issubset(result.registry["feature_cols"])
    assert set(cfg["new_feature_columns"]).issubset(result.registry["feature_cols"])
    forbidden = {"next_open", "exit_close_20d", "fwd_ret_20d", "target_class_20d", "label_valid_20d"}
    assert not (set(result.registry["feature_cols"]) & forbidden)


def test_expanded_output_only_label_valid_rows() -> None:
    base = _baseline_matrix(rows=80)
    base.loc[base.index[:3], "label_valid_20d"] = False
    result = build_expanded_features(base)
    assert len(result.data) == len(base) - 3


def test_expanded_no_ticker_crossing_and_days_since_causal() -> None:
    base = _baseline_matrix(rows=80).sort_values(["ticker", "date"]).reset_index(drop=True)
    result = build_expanded_features(base).data.sort_values(["ticker", "date"]).reset_index(drop=True)
    b = result[result["ticker"] == "B"].reset_index(drop=True)
    assert pd.isna(b.loc[0, "ret_2d"])
    changed_future = base.copy()
    changed_future.loc[changed_future.index[-1], "low"] = -9999
    changed = build_expanded_features(changed_future).data.sort_values(["ticker", "date"]).reset_index(drop=True)
    early = result["date"].astype(str) < "2010-03-01"
    pd.testing.assert_series_equal(
        result.loc[early, "days_since_20d_low"].reset_index(drop=True),
        changed.loc[early, "days_since_20d_low"].reset_index(drop=True),
        check_names=False,
    )


def test_expanded_cross_sectional_ranks_are_by_date_and_nulls_reported() -> None:
    result = build_expanded_features(_baseline_matrix()).data
    for _, g in result.groupby("date"):
        if g["rank_ret_5d_z_60d"].notna().any():
            vals = g["rank_ret_5d_z_60d"].dropna()
            assert vals.between(0, 1).all()
            break
    summary = build_expanded_features(_baseline_matrix(rows=80)).summary
    assert "ret_252d" in summary["null_counts"]
    assert summary["null_counts"]["ret_252d"] > 0
    assert summary["top_30_highest_null_features"]


def test_stage20_reads_only_parquet_when_registry_jsons_share_directory(tmp_path) -> None:
    paths = ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "data" / "raw_txt",
        raw_manifest=tmp_path / "data" / "raw_manifest" / "raw_manifest.parquet",
        validated=tmp_path / "data" / "validated",
        normalized=tmp_path / "data" / "normalized",
        causal=tmp_path / "data" / "causal",
        research_ohlcv_daily=tmp_path / "data" / "research_ohlcv_daily",
        labeled_target_h20=tmp_path / "data" / "labeled" / "target_h20",
        feature_matrix_baseline_h20=tmp_path / "data" / "feature_matrices" / "baseline_h20",
        feature_matrix_expanded_h20=tmp_path / "data" / "feature_matrices" / "expanded_h20",
        frozen_features_expanded_h20_v1=tmp_path / "data" / "frozen_features" / "expanded_h20_v1",
        oos_predictions_baseline_h20=tmp_path / "data" / "oos_predictions" / "baseline_h20",
        validation_reports=tmp_path / "reports" / "validation",
        label_reports=tmp_path / "reports" / "labels",
        feature_reports=tmp_path / "reports" / "features",
        wfa_reports=tmp_path / "reports" / "wfa",
        metrics_reports=tmp_path / "reports" / "metrics",
        gates_reports=tmp_path / "reports" / "gates",
    )
    paths.feature_matrix_baseline_h20.mkdir(parents=True)
    _baseline_matrix(rows=80).to_parquet(paths.feature_matrix_baseline_h20 / "baseline_h20.parquet", index=False)
    for name in ["feature_cols", "target_cols", "metadata_cols", "excluded_cols"]:
        (paths.feature_matrix_baseline_h20 / f"{name}.json").write_text("[]", encoding="utf-8")

    _, summary, registry = _run_polars(paths, load_expanded_feature_config())

    assert summary["output_rows"] > 0
    assert "ret_2d" in registry["feature_cols"]
