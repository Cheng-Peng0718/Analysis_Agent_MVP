from ui.renderers import (
    block_title,
    block_type,
    data_version_rows,
    metric_rows_from_payload,
    table_rows_from_payload,
    version_label,
    build_agent_activity_items,
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

def test_version_label_uses_version_id_and_creator():
    label = version_label({
        "version_id": "data_v0002",
        "created_by": "clean_data",
    })

    assert label == "data_v0002 · clean_data"


def test_data_version_rows_normalizes_versions_for_display():
    rows = data_version_rows([
        {
            "version_id": "raw_v1",
            "parent_version_id": None,
            "created_by": "upload",
            "n_rows": 5,
            "n_cols": 4,
            "description": "Initial upload.",
            "path": "workspace/data_versions/raw_v1.parquet",
        },
        {
            "version_id": "data_v0002",
            "parent_version_id": "raw_v1",
            "tool_name": "clean_data",
            "n_rows": 4,
            "n_cols": 4,
            "description": "Dropped rows with missing GPA.",
            "path": "workspace/data_versions/data_v0002.parquet",
        },
    ])

    assert rows[0]["version_id"] == "raw_v1"
    assert rows[0]["created_by"] == "upload"
    assert rows[1]["version_id"] == "data_v0002"
    assert rows[1]["parent_version_id"] == "raw_v1"
    assert rows[1]["tool_name"] == "clean_data"

def test_build_agent_activity_items_from_snapshot():
    items = build_agent_activity_items({
        "assistant_response": {
            "response_type": "final_answer",
        },
        "plan": {
            "plan_status": "completed",
        },
        "review": {
            "human_review_required": True,
            "pending_action": {
                "tool_name": "clean_data",
            },
        },
        "analysis": {
            "analysis_runs": [
                {
                    "tool_name": "clean_data",
                    "status": "ok",
                }
            ],
        },
        "dataset": {
            "active_data_version_id": "data_v123",
        },
    })

    assert "Response: `final_answer`" in items
    assert "Plan status: `completed`" in items
    assert "Review required for `clean_data`" in items
    assert "Last tool: `clean_data` · `ok`" in items
    assert "Active data: `data_v123`" in items