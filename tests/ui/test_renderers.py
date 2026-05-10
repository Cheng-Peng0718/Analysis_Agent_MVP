from ui.renderers import (
    block_title,
    block_type,
    metric_rows_from_payload,
    table_rows_from_payload,
)


def test_block_type_reads_common_keys():
    assert block_type({"type": "table"}) == "table"
    assert block_type({"block_type": "metric_table"}) == "metric_table"
    assert block_type({"kind": "text"}) == "text"
    assert block_type({}) == "unknown"


def test_block_title_reads_common_keys():
    assert block_title({"title": "Model summary"}) == "Model summary"
    assert block_title({"name": "Coefficients"}) == "Coefficients"
    assert block_title({"label": "Metrics"}) == "Metrics"
    assert block_title({}, fallback="Fallback") == "Fallback"


def test_table_rows_from_list_of_dicts():
    rows = table_rows_from_payload([
        {"term": "SATM", "estimate": 0.1},
        {"term": "Intercept", "estimate": 1.0},
    ])

    assert rows == [
        {"term": "SATM", "estimate": 0.1},
        {"term": "Intercept", "estimate": 1.0},
    ]


def test_table_rows_from_dict_rows_payload():
    rows = table_rows_from_payload({
        "rows": [
            {"term": "SATM", "estimate": 0.1},
        ]
    })

    assert rows == [
        {"term": "SATM", "estimate": 0.1},
    ]


def test_table_rows_from_metric_dict():
    rows = table_rows_from_payload({
        "r_squared": 0.72,
        "n_obs": 50,
    })

    assert {"metric": "r_squared", "value": 0.72} in rows
    assert {"metric": "n_obs", "value": 50} in rows


def test_metric_rows_from_payload():
    rows = metric_rows_from_payload({
        "r_squared": 0.72,
        "rmse": {
            "label": "RMSE",
            "value": 1.5,
        },
    })

    assert {"metric": "r_squared", "value": 0.72} in rows
    assert {"metric": "RMSE", "value": 1.5} in rows