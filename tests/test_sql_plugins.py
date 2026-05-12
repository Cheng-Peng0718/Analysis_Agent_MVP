from pathlib import Path

import duckdb


def _make_demo_db(tmp_path: Path) -> str:
    db_path = tmp_path / "demo.duckdb"

    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER,
            customer_id INTEGER,
            order_date DATE,
            revenue DOUBLE,
            region VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO orders VALUES
        (1, 101, '2024-01-01', 120.0, 'East'),
        (2, 102, '2024-01-03', 80.0, 'West'),
        (3, 101, '2024-02-01', 200.0, 'East')
        """
    )
    con.close()

    return str(db_path)


class DummyContext:
    def __init__(self, arguments, workspace_dir=None):
        self.arguments = arguments
        self.workspace_dir = workspace_dir
        self.active_data_version_id = None


def test_inspect_sql_schema_plugin(tmp_path):
    import core.analysis_tool_plugins.plugins  # noqa: F401
    from core.analysis_tool_plugins.registry import get_plugin

    db_path = _make_demo_db(tmp_path)

    plugin = get_plugin("inspect_sql_schema")
    assert plugin is not None

    result = plugin.run(DummyContext({"database_path": db_path}))

    assert result["status"] == "ok"
    assert result["details"]["n_tables"] == 1
    assert result["details"]["tables"][0]["table_name"] == "orders"


def test_run_sql_query_plugin_select(tmp_path):
    import core.analysis_tool_plugins.plugins  # noqa: F401
    from core.analysis_tool_plugins.registry import get_plugin

    db_path = _make_demo_db(tmp_path)

    plugin = get_plugin("run_sql_query")
    assert plugin is not None

    result = plugin.run(
        DummyContext(
            {
                "database_path": db_path,
                "query": "SELECT region, SUM(revenue) AS total_revenue FROM orders GROUP BY region ORDER BY region",
                "max_rows": 100,
            }
        )
    )

    assert result["status"] == "ok"
    assert result["details"]["n_rows_returned"] == 2
    assert "total_revenue" in result["details"]["columns"]


def test_run_sql_query_blocks_mutation(tmp_path):
    import core.analysis_tool_plugins.plugins  # noqa: F401
    from core.analysis_tool_plugins.registry import get_plugin

    db_path = _make_demo_db(tmp_path)

    plugin = get_plugin("run_sql_query")
    assert plugin is not None

    result = plugin.run(
        DummyContext(
            {
                "database_path": db_path,
                "query": "DROP TABLE orders",
            }
        )
    )

    assert result["status"] == "blocked"
    assert result["error_code"] == "UNSAFE_OR_INVALID_SQL"

def test_run_sql_query_through_execution_contract(tmp_path):
    import core.analysis_tool_plugins.plugins  # noqa: F401
    from core.schema import ActionProposal
    from core.analysis_tool_plugins.execution import execute_analysis_tool

    db_path = _make_demo_db(tmp_path)

    class DummyContextPackage:
        def __init__(self, workspace_dir):
            self.workspace_dir = str(workspace_dir)
            self.active_data_version_id = "sql_demo_v1"
            self.data_versions = []
            self.data_audit_log = []

    action = ActionProposal(
        action_id="act_sql_1",
        action_type="tool_call",
        tool_name="run_sql_query",
        arguments={
            "database_path": db_path,
            "query": "SELECT COUNT(*) AS n_orders, SUM(revenue) AS revenue FROM orders",
        },
        reasoning_summary="Run SQL KPI query.",
    )

    result = execute_analysis_tool(action, DummyContextPackage(tmp_path))

    assert result.tool_name == "run_sql_query"
    assert result.status == "ok"
    assert result.success is True
    assert result.data_version_id == "sql_demo_v1"
    assert "preview" in result.payload
    assert result.raw_payload["status"] == "ok"