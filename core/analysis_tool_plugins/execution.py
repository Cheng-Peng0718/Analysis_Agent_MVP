import uuid
from typing import Any, Dict

from core.schema import ActionProposal, ToolExecutionResult, AgentContext
from core.analysis_tool_plugins import get_plugin


_ALLOWED_STATUSES = {"ok", "warning", "blocked", "failed"}


def _as_dict(value: Any, *, fallback_key: str = "result") -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {fallback_key: value}


def _normalize_status(value: Any) -> str:
    status = str(value or "ok").strip().lower()
    if status not in _ALLOWED_STATUSES:
        return "failed"
    return status


def _normalize_artifacts(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_plugin_payload(result_payload: Any) -> Dict[str, Any]:
    """
    Normalize any plugin return value into the canonical execution payload.

    Plugin execute functions are allowed to return the compact plugin shape:

        {
            "status": "ok" | "warning" | "blocked" | "failed",
            "message": "...",
            "error_code": "...",
            "recoverable": bool,
            "details": {...},
            "artifacts": [...],
            "data_version_update": {...}  # optional
        }

    The workflow only consumes the canonical shape returned here.
    """
    raw_payload = _as_dict(result_payload)

    status = _normalize_status(raw_payload.get("status", "ok"))
    success = status in {"ok", "warning"}

    details = raw_payload.get("details", {})
    if not isinstance(details, dict):
        details = {"details": details}

    payload = dict(details)

    data_version_update = raw_payload.get("data_version_update")

    if data_version_update is None:
        maybe_details_update = details.get("data_version_update")
        if isinstance(maybe_details_update, dict):
            data_version_update = maybe_details_update

    if data_version_update is not None:
        payload["data_version_update"] = data_version_update

    for key in ["audit", "suggested_next_actions"]:
        if key in raw_payload:
            payload[key] = raw_payload[key]

    message = raw_payload.get("message")
    if message is None:
        if status == "ok":
            message = "Tool completed successfully."
        elif status == "warning":
            message = "Tool completed with warnings."
        elif status == "blocked":
            message = "Tool was blocked."
        else:
            message = "Tool failed."

    return {
        "status": status,
        "success": success,
        "error_code": raw_payload.get("error_code"),
        "message": message,
        "recoverable": bool(raw_payload.get("recoverable", status in {"blocked", "failed"})),
        "payload": payload,
        "artifacts": _normalize_artifacts(raw_payload.get("artifacts", [])),
        "data_version_update": data_version_update,
        "raw_payload": raw_payload,
    }


def execute_analysis_tool(action: ActionProposal, context_pkg) -> ToolExecutionResult:
    """
    Unified execution entrypoint.

    Priority:
    1. Execute unified AnalysisToolPlugin if available and it defines execute.
    2. Execute registered AnalysisToolPlugin only.

    This keeps the migration safe while allowing new tools to live only in
    core.analysis_tool_plugins.plugins.
    """
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    tool_name = action.tool_name

    try:
        workspace_dir = getattr(context_pkg, "workspace_dir", "./")

        context = AgentContext(
            workspace_dir=workspace_dir,
            arguments=action.arguments,
            data_versions=getattr(context_pkg, "data_versions", []) or [],
            active_data_version_id=getattr(context_pkg, "active_data_version_id", None),
            data_audit_log=getattr(context_pkg, "data_audit_log", []) or [],
            analysis_runs=getattr(context_pkg, "analysis_runs", []) or [],
        )

        print(f"Running tool: {tool_name}, arguments: {action.arguments}")

        plugin = get_plugin(tool_name)

        if plugin is None:
            raise ValueError(
                f"Tool `{tool_name}` is not registered in core.analysis_tool_plugins."
            )

        if plugin.execute is None:
            raise ValueError(
                f"Tool `{tool_name}` is registered but does not define an execute function."
            )

        result_payload = plugin.run(context)

        normalized = _normalize_plugin_payload(result_payload)

        input_data_version_id = getattr(context, "active_data_version_id", None)

        return ToolExecutionResult(
            execution_id=execution_id,
            action_id=action.action_id,
            tool_name=tool_name,
            success=normalized["success"],
            status=normalized["status"],
            error_code=normalized["error_code"],
            message=normalized["message"],
            recoverable=normalized["recoverable"],
            data_version_id=input_data_version_id,
            data_version_update=normalized["data_version_update"],
            payload=normalized["payload"],
            artifacts=normalized["artifacts"],
            raw_payload=normalized["raw_payload"],
        )

    except Exception as e:
        print(f"❌ Tool execution crashed: {str(e)}")

        return ToolExecutionResult(
            execution_id=execution_id,
            action_id=action.action_id,
            tool_name=tool_name,
            success=False,
            status="failed",
            error_code="TOOL_EXECUTION_EXCEPTION",
            message=f"Tool execution crashed: {str(e)}",
            recoverable=True,
            data_version_id=getattr(context_pkg, "active_data_version_id", None),
            data_version_update=None,
            payload={
                "error_message": str(e),
                "exception_type": type(e).__name__,
            },
            artifacts=[],
            raw_payload={
                "exception_type": type(e).__name__,
                "exception_message": str(e),
            },
        )

def execute_tool(action: ActionProposal, context_pkg) -> ToolExecutionResult:
    """
    Canonical execution adapter for the workflow graph.

    This replaces the legacy tools.execution.execute_tool wrapper.
    """
    return execute_analysis_tool(action, context_pkg)