import pandas as pd

from core.analysis_tool_plugins.shared.regression_utils import prepare_regression_data


def test_prepare_regression_data_numeric_predictor_ok():
    df = pd.DataFrame({
        "y": [1.0, 2.0, 3.0, 4.0, 5.0],
        "x": [2.0, 4.0, 6.0, 8.0, 10.0],
    })

    result = prepare_regression_data(
        df=df,
        target_col="y",
        feature_cols=["x"],
        min_n_per_parameter=1,
    )

    assert result["status"] == "ok"
    assert "y" in result
    assert "X" in result
    assert result["details"]["n_eff"] == 5
    assert result["details"]["p_eff"] == 1
    assert result["X"].shape == (5, 1)


def test_prepare_regression_data_blocks_missing_target():
    df = pd.DataFrame({
        "y": [1.0, 2.0, 3.0],
        "x": [1.0, 2.0, 3.0],
    })

    result = prepare_regression_data(
        df=df,
        target_col=None,
        feature_cols=["x"],
    )

    assert result["status"] == "blocked"
    assert result["error_code"] == "MISSING_TARGET"


def test_prepare_regression_data_blocks_missing_feature_column():
    df = pd.DataFrame({
        "y": [1.0, 2.0, 3.0],
        "x": [1.0, 2.0, 3.0],
    })

    result = prepare_regression_data(
        df=df,
        target_col="y",
        feature_cols=["z"],
    )

    assert result["status"] == "blocked"
    assert result["error_code"] == "COLUMNS_NOT_FOUND"


def test_prepare_regression_data_encodes_categorical_predictor():
    df = pd.DataFrame({
        "y": [1, 2, 3, 4, 5, 6],
        "group": ["a", "a", "b", "b", "c", "c"],
    })

    result = prepare_regression_data(
        df=df,
        target_col="y",
        feature_cols=["group"],
        min_n_per_parameter=1,
    )

    assert result["status"] == "ok"
    assert result["details"]["p_eff"] == 2
    assert result["X"].shape[1] == 2