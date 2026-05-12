# core/analysis_tool_plugins/plugins/run_sql_query.py

from __future__ import annotations

from typing import Any

from core.analysis_tool_plugins.base import AnalysisToolPlugin, ArgumentSchema
from core.analysis_tool_plugins.registry import register_plugin
from core.analysis_tool_plugins.shared.sql_utils import (
    connect_duckdb_read_only,
    dataframe_preview_payload,
    limit_query,
    normalize_database_path,
    validate_read_only_sql,
)


DEFAULT_MAX_ROWS = 500


def _execute(context) -> dict[str, Any]:
    arguments = (
            getattr(context, "arguments", None)
            or getattr(context, "args", None)
            or {}
    )

    database_path = arguments.get("database_path")
    query = arguments.get("query")
    max_rows = arguments.get("max_rows", DEFAULT_MAX_ROWS)
    workspace_dir = getattr(context, "workspace_dir", None)

    try:
        max_rows = int(max_rows)
    except Exception:
        max_rows = DEFAULT_MAX_ROWS

    max_rows = max(1, min(max_rows, 5000))

    is_safe, safety_error = validate_read_only_sql(query)

    if not is_safe:
        return {
            "status": "blocked",
            "error_code": "UNSAFE_OR_INVALID_SQL",
            "message": safety_error,
            "recoverable": True,
            "details": {
                "query": query,
                "safety_error": safety_error,
            },
            "artifacts": [],
        }

    try:
        resolved_path = normalize_database_path(database_path, workspace_dir=workspace_dir)
        limited_query = limit_query(query, max_rows=max_rows)

        con = connect_duckdb_read_only(resolved_path)
        df = con.execute(limited_query).fetchdf()
        con.close()

        payload = dataframe_preview_payload(df)

        payload.update(
            {
                "database_path": resolved_path,
                "query": query,
                "executed_query": limited_query,
                "max_rows": max_rows,
            }
        )

        return {
            "status": "ok",
            "message": (
                f"SQL query executed successfully. "
                f"Returned {payload['n_rows_returned']} row(s) and {payload['n_cols_returned']} column(s)."
            ),
            "recoverable": False,
            "details": payload,
            "artifacts": [],
        }

    except Exception as exc:
        return {
            "status": "failed",
            "error_code": "SQL_QUERY_EXECUTION_FAILED",
            "message": f"SQL query execution failed: {exc}",
            "recoverable": True,
            "details": {
                "database_path": database_path,
                "query": query,
                "exception_type": type(exc).__name__,
                "error_message": str(exc),
            },
            "artifacts": [],
        }


run_sql_query_plugin = AnalysisToolPlugin(
    tool_name="run_sql_query",
    display_name="Run Safe SQL Query",
    execute=_execute,
    argument_schema=ArgumentSchema(
        required={
            "database_path": str,
            "query": str,
        },
        optional={
            "max_rows": int,
        },
    ),
    requires_confirmation=False,
)

register_plugin(run_sql_query_plugin)