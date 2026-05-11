from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pandas as pd
import streamlit as st


def render_json_expander(
    title: str,
    payload: Any,
    *,
    expanded: bool = False,
) -> None:
    with st.expander(title, expanded=expanded):
        st.json(payload)


def rows_from_column_profile(columns: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []

    for name, meta in columns.items():
        rows.append({
            "column": name,
            "semantic_type": meta.get("semantic_type", "unknown"),
            "dtype": meta.get("dtype", "unknown"),
            "missing_rate": meta.get("missing_rate", 0.0),
            "n_unique": meta.get("n_unique"),
        })

    return rows


def render_key_value_captions(items: Iterable[tuple[str, Any]]) -> None:
    for label, value in items:
        st.caption(f"{label}: `{value}`")


def block_type(block: Dict[str, Any]) -> str:
    return str(
        block.get("type")
        or block.get("block_type")
        or block.get("kind")
        or "unknown"
    )


def block_title(block: Dict[str, Any], fallback: str = "Result") -> str:
    return str(
        block.get("title")
        or block.get("name")
        or block.get("label")
        or fallback
    )


def table_rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    """
    Normalize common table payload shapes into dataframe-friendly rows.
    """
    if payload is None:
        return []

    if isinstance(payload, list):
        if all(isinstance(row, dict) for row in payload):
            return payload

        return [{"value": item} for item in payload]

    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            rows = payload["rows"]

            if all(isinstance(row, dict) for row in rows):
                return rows

            return [{"value": row} for row in rows]

        if isinstance(payload.get("data"), list):
            data = payload["data"]

            if all(isinstance(row, dict) for row in data):
                return data

            return [{"value": row} for row in data]

        return [
            {
                "metric": key,
                "value": value,
            }
            for key, value in payload.items()
        ]

    return [{"value": payload}]


def metric_rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []

    if isinstance(payload, dict):
        rows = []

        for key, value in payload.items():
            if isinstance(value, dict):
                rows.append({
                    "metric": value.get("label") or key,
                    "value": value.get("value"),
                })
            else:
                rows.append({
                    "metric": key,
                    "value": value,
                })

        return rows

    if isinstance(payload, list):
        return table_rows_from_payload(payload)

    return [{"metric": "value", "value": payload}]


def render_table_payload(payload: Any) -> None:
    rows = table_rows_from_payload(payload)

    if not rows:
        st.caption("No table rows available.")
        return

    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
    )


def render_metric_payload(payload: Any) -> None:
    rows = metric_rows_from_payload(payload)

    if not rows:
        st.caption("No metrics available.")
        return

    if len(rows) <= 4:
        cols = st.columns(len(rows))

        for col, row in zip(cols, rows):
            col.metric(
                str(row.get("metric")),
                row.get("value", "—"),
            )

        return

    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
    )


def render_artifact_payload(payload: Any) -> None:
    artifacts = payload

    if isinstance(payload, dict):
        artifacts = payload.get("artifacts") or payload.get("files") or [payload]

    if not isinstance(artifacts, list):
        artifacts = [artifacts]

    if not artifacts:
        st.caption("No artifacts available.")
        return

    for artifact in artifacts:
        if isinstance(artifact, dict):
            label = artifact.get("label") or artifact.get("name") or artifact.get("path")
            path = artifact.get("path") or artifact.get("file_path")
            kind = artifact.get("kind") or artifact.get("type")

            st.write(f"**{label or 'Artifact'}**")
            if kind:
                st.caption(f"Kind: `{kind}`")
            if path:
                st.code(str(path))
        else:
            st.write(artifact)


def render_report_block(block: Dict[str, Any]) -> None:
    kind = block_type(block)
    title = block_title(block, fallback=kind)

    payload = (
        block.get("payload")
        or block.get("data")
        or block.get("rows")
        or block.get("content")
        or block
    )

    with st.expander(title, expanded=True):
        if kind in {"text", "markdown", "summary"}:
            st.markdown(str(payload))
            return

        if kind in {"metric", "metrics", "metric_table"}:
            render_metric_payload(payload)
            return

        if kind in {"table", "dataframe", "json_table"}:
            render_table_payload(payload)
            return

        if kind in {"artifact", "artifacts", "figure", "plot"}:
            render_artifact_payload(payload)
            return

        st.json(block)


def render_report_blocks(blocks: List[Dict[str, Any]]) -> None:
    if not blocks:
        st.caption("No report blocks available.")
        return

    for block in blocks:
        if isinstance(block, dict):
            render_report_block(block)
        else:
            st.write(block)


def render_analysis_run(run: Dict[str, Any]) -> None:
    title = run.get("tool_name") or run.get("run_id") or "Analysis run"
    status = run.get("status")

    with st.expander(f"{title} · {status}", expanded=True):
        if run.get("summary"):
            st.markdown(run["summary"])

        report_blocks = run.get("report_blocks") or []
        if report_blocks:
            render_report_blocks(report_blocks)

        if run.get("metrics"):
            st.markdown("**Metrics**")
            render_metric_payload(run["metrics"])

        if run.get("tables"):
            st.markdown("**Tables**")
            render_table_payload(run["tables"])

        if run.get("artifacts"):
            st.markdown("**Artifacts**")
            render_artifact_payload(run["artifacts"])

def version_label(version: Dict[str, Any]) -> str:
    version_id = version.get("version_id") or "unknown_version"
    created_by = version.get("created_by") or version.get("tool_name") or "unknown"

    return f"{version_id} · {created_by}"


def data_version_rows(versions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []

    for version in versions:
        rows.append({
            "version_id": version.get("version_id"),
            "parent_version_id": version.get("parent_version_id"),
            "created_by": version.get("created_by"),
            "tool_name": version.get("tool_name"),
            "n_rows": version.get("n_rows"),
            "n_cols": version.get("n_cols"),
            "description": version.get("description"),
            "path": version.get("path"),
        })

    return rows


def render_data_version_timeline(
    versions: List[Dict[str, Any]],
    *,
    active_version_id: str | None = None,
) -> None:
    if not versions:
        st.info("No data versions yet.")
        return

    st.dataframe(
        pd.DataFrame(data_version_rows(versions)),
        width="stretch",
        hide_index=True,
    )

    st.markdown("**Timeline**")

    for index, version in enumerate(versions):
        version_id = version.get("version_id") or "unknown_version"
        is_active = version_id == active_version_id

        badge = "🟢 Active" if is_active else "⚪ Version"
        parent = version.get("parent_version_id")
        created_by = version.get("created_by") or version.get("tool_name") or "unknown"
        description = version.get("description") or ""

        with st.container(border=True):
            st.markdown(f"**{badge}: `{version_id}`**")
            st.caption(f"Created by: `{created_by}`")

            if parent:
                st.caption(f"Parent: `{parent}`")

            cols = st.columns(2)
            cols[0].metric("Rows", version.get("n_rows", "—"))
            cols[1].metric("Columns", version.get("n_cols", "—"))

            if description:
                st.write(description)

            path = version.get("path")
            if path:
                with st.expander("Stored path", expanded=False):
                    st.code(str(path))

        if index < len(versions) - 1:
            st.markdown("↓")

def compact_version_node(
    version: Dict[str, Any],
    *,
    active_version_id: str | None = None,
) -> str:
    version_id = version.get("version_id") or "unknown"
    is_active = version_id == active_version_id
    icon = "🟢" if is_active else "⚪"
    short_id = version_id

    if len(short_id) > 14:
        short_id = short_id[:11] + "..."

    return f"{icon} `{short_id}`"


def compact_version_dot(
    version: Dict[str, Any],
    *,
    active_version_id: str | None = None,
) -> str:
    version_id = version.get("version_id")
    return "🟢" if version_id == active_version_id else "⚪"

def render_compact_data_version_timeline(
    versions: List[Dict[str, Any]],
    *,
    active_version_id: str | None = None,
) -> None:
    if not versions:
        st.caption("No versions yet.")
        return

    dots = " —— ".join(
        compact_version_dot(version, active_version_id=active_version_id)
        for version in versions
    )

    st.markdown(f"**{dots}**")

    active_version = next(
        (
            version
            for version in versions
            if version.get("version_id") == active_version_id
        ),
        None,
    )

    if not active_version:
        return

    created_by = (
        active_version.get("created_by")
        or active_version.get("tool_name")
        or "unknown"
    )
    n_rows = active_version.get("n_rows", "—")
    n_cols = active_version.get("n_cols", "—")

    st.caption(
        f"Active `{active_version_id}` · {created_by} · "
        f"{n_rows} rows × {n_cols} cols"
    )

    if len(versions) > 1:
        with st.expander("Version details", expanded=False):
            for version in versions:
                version_id = version.get("version_id")
                marker = "🟢" if version_id == active_version_id else "⚪"
                creator = version.get("created_by") or version.get("tool_name") or "unknown"
                rows = version.get("n_rows", "—")
                cols = version.get("n_cols", "—")
                st.caption(f"{marker} `{version_id}` · {creator} · {rows} × {cols}")


def build_agent_activity_items(snapshot: Dict[str, Any]) -> List[str]:
    items = []

    assistant_response = snapshot.get("assistant_response") or {}
    response_type = assistant_response.get("response_type")
    if response_type:
        items.append(f"Response: `{response_type}`")

    plan = snapshot.get("plan") or {}
    if plan.get("plan_status"):
        items.append(f"Plan status: `{plan.get('plan_status')}`")

    review = snapshot.get("review") or {}
    if review.get("human_review_required"):
        pending_action = review.get("pending_action") or {}
        tool_name = pending_action.get("tool_name") or "unknown_tool"
        items.append(f"Review required for `{tool_name}`")

    analysis = snapshot.get("analysis") or {}
    runs = analysis.get("analysis_runs") or []
    if runs:
        last_run = runs[-1]
        tool_name = last_run.get("tool_name") or "unknown_tool"
        status = last_run.get("status")
        items.append(f"Last tool: `{tool_name}` · `{status}`")

    dataset = snapshot.get("dataset") or {}
    active_version = dataset.get("active_data_version_id")
    if active_version:
        items.append(f"Active data: `{active_version}`")

    return items


def render_agent_activity(snapshot: Dict[str, Any]) -> None:
    items = build_agent_activity_items(snapshot)

    if not items:
        return

    with st.expander("Agent Activity", expanded=False):
        for item in items:
            st.markdown(f"- {item}")