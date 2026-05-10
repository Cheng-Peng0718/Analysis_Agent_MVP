from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.analysis_tool_plugins.display import (
    DisplayConfig,
    MetricDisplayConfig,
    TableDisplayConfig,
    clean_metric_value,
    humanize_key,
)


def metric_rows_from_dict_with_display(
    metrics: Dict[str, Any],
    config: MetricDisplayConfig,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    metrics = metrics or {}

    ordered_keys: List[str] = []

    for key in config.order or []:
        if key in metrics and key not in ordered_keys:
            ordered_keys.append(key)

    for key in metrics.keys():
        if key not in ordered_keys:
            ordered_keys.append(key)

    for key in ordered_keys:
        value = metrics.get(key)

        if value is None:
            continue

        label = config.labels.get(key, humanize_key(key))
        formatter = config.formatters.get(key)
        display_value = formatter(value) if formatter else clean_metric_value(value)

        rows.append({
            "label": label,
            "value": display_value,
            "raw_key": key,
        })

    return rows


def normalize_table_from_list_with_display(
    rows: List[Dict[str, Any]],
    config: TableDisplayConfig,
) -> Dict[str, Any]:
    if not rows:
        return {"columns": [], "rows": []}

    raw_columns: List[str] = []

    for key in config.column_order or []:
        if key not in raw_columns:
            raw_columns.append(key)

    for row in rows:
        if isinstance(row, dict):
            for key in row.keys():
                if key not in raw_columns:
                    raw_columns.append(key)

    columns = [
        {
            "label": config.column_labels.get(col, humanize_key(col)),
            "raw_key": col,
        }
        for col in raw_columns
    ]

    normalized_rows = []

    for row in rows:
        normalized_row = []

        for col in raw_columns:
            value = row.get(col, "") if isinstance(row, dict) else ""

            if col in config.value_mappers:
                value = config.value_mappers[col].get(value, value)

            formatter = config.column_formatters.get(col)
            value = formatter(value) if formatter else clean_metric_value(value)
            normalized_row.append(value)

        normalized_rows.append(normalized_row)

    return {
        "columns": columns,
        "rows": normalized_rows,
    }


def build_generic_report_blocks(
    *,
    summary: str,
    metrics: Dict[str, Any],
    tables: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    display_config: Optional[DisplayConfig] = None,
) -> List[Dict[str, Any]]:
    display_config = display_config or DisplayConfig()
    blocks: List[Dict[str, Any]] = []

    if summary:
        blocks.append({
            "type": "text",
            "title": "Summary",
            "content": summary,
        })

    metric_rows = metric_rows_from_dict_with_display(
        metrics or {},
        display_config.metrics,
    )

    if metric_rows:
        blocks.append({
            "type": "metric_table",
            "title": "Metrics",
            "rows": metric_rows,
        })

    for table_name, table_data in (tables or {}).items():
        table_display = display_config.tables.get(table_name, TableDisplayConfig())

        if isinstance(table_data, list) and all(isinstance(x, dict) for x in table_data):
            normalized = normalize_table_from_list_with_display(
                table_data,
                table_display,
            )

            blocks.append({
                "type": "table",
                "title": humanize_key(table_name),
                "columns": normalized["columns"],
                "rows": normalized["rows"],
            })

        elif isinstance(table_data, dict):
            blocks.append({
                "type": "json",
                "title": humanize_key(table_name),
                "content": table_data,
            })

        else:
            blocks.append({
                "type": "text",
                "title": humanize_key(table_name),
                "content": str(table_data),
            })

    for artifact in artifacts or []:
        artifact_type = artifact.get("type")

        if artifact_type in {"png", "jpg", "jpeg"}:
            blocks.append({
                "type": "figure",
                "title": artifact.get("name") or "Figure",
                "path": artifact.get("path"),
                "name": artifact.get("name"),
                "artifact_type": artifact_type,
            })
        else:
            blocks.append({
                "type": "artifact",
                "title": artifact.get("name") or "Artifact",
                "content": artifact,
            })

    return blocks


def default_extractor(
    *,
    tool_name: str,
    payload: Dict[str, Any],
    arguments: Dict[str, Any],
    default_title: str,
    default_summary: str,
) -> Tuple[str, str, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    title = default_title
    summary = default_summary
    metrics: Dict[str, Any] = {}
    tables: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}

    if isinstance(payload, dict) and payload:
        tables["payload"] = payload

    return title, summary, metrics, tables, metadata
