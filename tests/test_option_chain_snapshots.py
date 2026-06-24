from pathlib import Path

import pandas as pd
import pytest

from quant_project_daily.config import ProjectPaths
from quant_project_daily.option_chain_snapshots import (
    CORE_REQUIRED_COLUMNS,
    MANUAL_TEMPLATE_COLUMNS,
    OPTION_CHAIN_SCHEMA,
    import_option_chain_manifest,
    import_option_chain_snapshot,
    link_option_chains_to_candidates,
    normalize_option_chain_snapshot,
)


def _paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "raw_txt",
        raw_manifest=tmp_path / "raw_manifest",
        validated=tmp_path / "validated",
        normalized=tmp_path / "normalized",
        causal=tmp_path / "causal",
        research_ohlcv_daily=tmp_path / "research_ohlcv_daily",
        labeled_target_h5=tmp_path / "targets",
        feature_matrix_baseline_h5=tmp_path / "feature_matrix_baseline_h5",
        feature_matrix_expanded_h5=tmp_path / "feature_matrix_expanded_h5",
        frozen_features_expanded_h5_v1=tmp_path / "frozen",
        oos_predictions_baseline_h5=tmp_path / "oos",
        validation_reports=tmp_path / "validation_reports",
        label_reports=tmp_path / "label_reports",
        feature_reports=tmp_path / "feature_reports",
        wfa_reports=tmp_path / "wfa_reports",
        metrics_reports=tmp_path / "metrics_reports",
        gates_reports=tmp_path / "gates_reports",
        signals_reports=tmp_path / "signals",
        option_chain_normalized=tmp_path / "data" / "options" / "normalized",
        option_chain_raw_snapshots=tmp_path / "data" / "options" / "raw_snapshots",
        option_chain_candidate_linked=tmp_path / "data" / "options" / "candidate_linked",
        option_chain_reports=tmp_path / "reports" / "options",
    )


def _raw_fixture() -> pd.DataFrame:
    return pd.read_csv(Path("tests/fixtures/manual_option_chain_snapshot.csv"))


def _candidates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "score_date": "2026-05-29",
                "ticker": "AAA",
                "raw_ticker": "AAA.US",
                "signal_side": "bullish_candidate",
                "signal_decile": 10,
                "pred_score_5d": 1.2,
                "pred_rank_pct_by_date": 0.99,
                "passes_option_underlying_proxy_25m": True,
                "passes_option_underlying_proxy_50m": True,
            },
            {
                "score_date": "2026-05-29",
                "ticker": "BBB",
                "raw_ticker": "BBB.US",
                "signal_side": "bearish_candidate",
                "signal_decile": 1,
                "pred_score_5d": -1.2,
                "pred_rank_pct_by_date": 0.01,
                "passes_option_underlying_proxy_25m": True,
                "passes_option_underlying_proxy_50m": False,
            },
        ]
    )


def _manual_template_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "snapshot_date": "2026-06-24",
                "snapshot_time": "15:45:00",
                "underlying": "AMD",
                "expiration": "2026-07-17",
                "dte": "",
                "option_type": "CALL",
                "strike": 500,
                "bid": 43.70,
                "ask": 44.75,
                "mid": "",
                "last": 44.83,
                "volume": 230,
                "open_interest": 5800,
                "implied_volatility": 0.7253,
                "delta": 0.5954,
                "gamma": 0.0041,
                "theta": -0.7885,
                "vega": 0.4996,
                "source": "etrade_power_web",
                "source_symbol": "AMD---260717C00500000",
            }
        ],
        columns=MANUAL_TEMPLATE_COLUMNS,
    )


def test_normalize_option_chain_snapshot_adds_optional_nulls_and_computes_fields() -> None:
    normalized, missing_optional = normalize_option_chain_snapshot(_raw_fixture())

    assert list(normalized.columns) == OPTION_CHAIN_SCHEMA
    assert len(normalized) == 3
    assert normalized.loc[normalized["option_symbol"] == "AAA260619P00100000", "mid"].item() == pytest.approx(3.0)
    assert normalized.loc[normalized["option_symbol"] == "AAA260619P00100000", "DTE"].item() == 18
    assert missing_optional["data_delay_status"] == 3
    assert missing_optional["snapshot_timestamp"] == 3
    assert normalized["volume"].isna().sum() == 1
    assert normalized["open_interest"].isna().sum() == 1


def test_normalize_option_chain_snapshot_accepts_manual_template_columns() -> None:
    normalized, missing_optional = normalize_option_chain_snapshot(_manual_template_fixture())

    row = normalized.iloc[0]
    assert list(normalized.columns) == OPTION_CHAIN_SCHEMA
    assert row["underlying_ticker"] == "AMD"
    assert row["option_symbol"] == "AMD---260717C00500000"
    assert row["data_source"] == "etrade_power_web"
    assert row["call_put"] == "C"
    assert row["DTE"] == 23
    assert row["mid"] == pytest.approx((43.70 + 44.75) / 2.0)
    assert str(row["snapshot_timestamp"]) == "2026-06-24 15:45:00"
    assert missing_optional["data_delay_status"] == 1


def test_normalize_option_chain_snapshot_requires_core_columns() -> None:
    raw = _raw_fixture().drop(columns=["bid"])
    with pytest.raises(ValueError, match="missing required option-chain columns"):
        normalize_option_chain_snapshot(raw)
    assert "bid" in CORE_REQUIRED_COLUMNS


def test_normalize_option_chain_snapshot_rejects_null_core_values() -> None:
    raw = _raw_fixture()
    raw.loc[0, "data_source"] = ""
    with pytest.raises(ValueError, match="required option-chain values contain nulls"):
        normalize_option_chain_snapshot(raw)


def test_normalize_option_chain_snapshot_rejects_negative_volume_or_open_interest() -> None:
    raw = _manual_template_fixture()
    raw.loc[0, "volume"] = -1
    with pytest.raises(ValueError, match="volume and open_interest must be non-negative"):
        normalize_option_chain_snapshot(raw)


def test_normalize_option_chain_snapshot_rejects_expiration_on_or_before_snapshot_date() -> None:
    raw = _manual_template_fixture()
    raw.loc[0, "expiration"] = "2026-06-24"
    with pytest.raises(ValueError, match="expiration must be after snapshot_date"):
        normalize_option_chain_snapshot(raw)


def test_link_option_chains_to_candidates_preserves_score_and_snapshot_dates() -> None:
    normalized, _ = normalize_option_chain_snapshot(_raw_fixture())
    linked, linkage = link_option_chains_to_candidates(normalized, _candidates())

    aaa = linked[linked["underlying_ticker"] == "AAA"]
    assert set(aaa["score_date"].astype(str)) == {"2026-05-29"}
    assert set(aaa["snapshot_date"].astype(str)) == {"2026-06-01"}
    assert not aaa["snapshot_matches_score_date"].any()
    assert linkage["candidate_tickers_without_option_rows"] == ["BBB"]
    assert linkage["option_chain_tickers_not_in_candidates"] == ["ZZZ"]
    assert linkage["unlinked_option_rows"] == 1


def test_import_option_chain_snapshot_writes_outputs_and_summary(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.signals_reports.mkdir(parents=True)
    candidate_path = paths.signals_reports / "baseline_h5_daily_underlying_candidates.csv"
    _candidates().to_csv(candidate_path, index=False)

    summary = import_option_chain_snapshot(
        Path("tests/fixtures/manual_option_chain_snapshot.csv"),
        paths=paths,
        candidates_path=candidate_path,
    )

    assert Path(summary["normalized_output_path"]).exists()
    assert Path(summary["raw_snapshot_output_path"]).exists()
    assert Path(summary["candidate_linked_output_path"]).exists()
    assert Path(summary["summary_output_path"]).exists()
    assert summary["missing_optional_field_counts"]["data_delay_status"] == 3
    assert summary["linkage"]["candidate_tickers_without_option_rows"] == ["BBB"]
    assert summary["linkage"]["option_chain_tickers_not_in_candidates"] == ["ZZZ"]
    assert summary["snapshot_date_equals_score_date"] is False


def test_import_option_chain_manifest_writes_batch_reports_and_failures(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.signals_reports.mkdir(parents=True)
    candidate_path = paths.signals_reports / "baseline_h5_daily_underlying_candidates.csv"
    _candidates().to_csv(candidate_path, index=False)

    summary = import_option_chain_manifest(
        Path("tests/fixtures/stage17_manual_snapshot_manifest.csv"),
        paths=paths,
        candidates_path=candidate_path,
    )

    coverage_path = Path(summary["candidate_coverage_output_path"])
    failures_path = Path(summary["batch_failures_output_path"])
    summary_path = Path(summary["batch_summary_output_path"])
    assert coverage_path.exists()
    assert failures_path.exists()
    assert summary_path.exists()
    assert summary["manifest_rows"] == 3
    assert summary["succeeded_files"] == 2
    assert summary["failed_files"] == 1
    assert summary["total_input_rows"] == 3
    assert summary["total_normalized_rows"] == 3
    assert summary["total_candidate_linked_rows"] == 3
    assert summary["invalid_or_quarantined_rows"] == 0
    assert summary["candidate_coverage"]["candidate_tickers"] == 2
    assert summary["candidate_coverage"]["candidate_tickers_covered"] == 1
    assert summary["candidate_coverage"]["candidate_tickers_without_chain_rows"] == ["BBB"]
    assert summary["candidate_coverage"]["option_chain_tickers_not_in_candidates"] == ["ZZZ"]
    assert summary["candidate_coverage"]["linked_rows"] == 2
    assert summary["candidate_coverage"]["unlinked_option_rows"] == 1
    assert summary["failures"][0]["underlying"] == "CCC"
    assert "ask must be greater than or equal to bid" in summary["failures"][0]["error"]

    coverage = pd.read_csv(coverage_path)
    aaa = coverage.loc[coverage["ticker"] == "AAA"].iloc[0]
    bbb = coverage.loc[coverage["ticker"] == "BBB"].iloc[0]
    assert aaa["snapshot_count"] == 1
    assert aaa["contract_row_count"] == 2
    assert aaa["snapshot_dates"] == "2026-06-01"
    assert aaa["latest_snapshot_date"] == "2026-06-01"
    assert bool(aaa["snapshot_matches_score_date_any"]) is False
    assert bool(aaa["options_liquidity_verified"]) is False
    assert bbb["snapshot_count"] == 0
    assert bbb["contract_row_count"] == 0

    failures = pd.read_csv(failures_path)
    assert len(failures) == 1
    assert failures.loc[0, "underlying"] == "CCC"
