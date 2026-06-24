from pathlib import Path

import pandas as pd
import pytest

from quant_project_daily.config import ProjectPaths
from quant_project_daily.option_chain_snapshots import (
    CORE_REQUIRED_COLUMNS,
    OPTION_CHAIN_SCHEMA,
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
