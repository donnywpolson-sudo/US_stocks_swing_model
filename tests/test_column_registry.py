from quant_project_daily.column_registry import build_column_registry


def test_column_registry_separates_features_targets_metadata_and_excluded() -> None:
    cfg = {
        "feature_columns": ["ret_1d", "rsi_14"],
        "target_columns": ["target_class_5d", "fwd_ret_5d"],
        "metadata_columns": ["date", "ticker"],
        "excluded_columns": ["next_open"],
    }
    columns = ["date", "ticker", "next_open", "target_class_5d", "fwd_ret_5d", "ret_1d", "rsi_14", "extra"]
    reg = build_column_registry(columns, cfg)
    assert reg["feature_cols"] == ["ret_1d", "rsi_14"]
    assert reg["target_cols"] == ["target_class_5d", "fwd_ret_5d"]
    assert reg["metadata_cols"] == ["date", "ticker"]
    assert reg["excluded_cols"] == ["next_open", "extra"]
    assert not (set(reg["feature_cols"]) & set(reg["target_cols"]) & set(reg["excluded_cols"]))
