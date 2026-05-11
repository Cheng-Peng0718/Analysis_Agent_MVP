from __future__ import annotations

from typing import Any, Iterable

from core.workflow.runtime_utils import get_action_hash


NON_EXECUTION_ERROR_CODES = {
    "HUMAN_CONFIRMATION_REQUIRED",
    "HUMAN_REVIEW_REJECTED",
    "VERIFICATION_FAILED",
    "MISSING_REVIEW_STATE",
    "UNHANDLED_HUMAN_REVIEW_STATUS",
}


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    return {}


def _data_version_id_from_payload(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return None

    direct = (
        payload.get("data_version_id")
        or payload.get("active_data_version_id")
    )
    if direct:
        return str(direct)

    for key in ["metadata", "structured_data", "raw_data", "payload"]:
        nested = payload.get(key)
        if not isinstance(nested, dict):
            continue

        nested_value = (
            nested.get("data_version_id")
            or nested.get("active_data_version_id")
        )
        if nested_value:
            return str(nested_value)

        nested_payload = nested.get("payload")
        if isinstance(nested_payload, dict):
            nested_payload_value = (
                nested_payload.get("data_version_id")
                or nested_payload.get("active_data_version_id")
            )
            if nested_payload_value:
                return str(nested_payload_value)

    return None


def _looks_like_real_execution_observation(obs: dict) -> bool:
    if not isinstance(obs, dict):
        return False

    if not obs.get("tool_name"):
        return False

    error_code = obs.get("error_code")
    if error_code in NON_EXECUTION_ERROR_CODES:
        return False

    raw_data = obs.get("raw_data") or {}
    structured_data = obs.get("structured_data") or {}

    if isinstance(raw_data, dict) and raw_data.get("execution_id"):
        return True

    if isinstance(structured_data, dict):
        payload = structured_data.get("payload") or {}
        if isinstance(payload, dict) and payload:
            return True

    return obs.get("success") is not None and obs.get("status") in {
        "ok",
        "warning",
        "failed",
        "blocked",
    }


def iter_executed_action_records(state: dict) -> Iterable[dict]:
    """
    Yield executed action records scoped by data version.

    Duplicate execution should only block the same tool+arguments on the same
    active data version. The same tool+arguments on a new data version is valid.
    """
    seen = set()

    for run in state.get("analysis_runs", []) or []:
        run_dict = _as_dict(run)
        tool_name = run_dict.get("tool_name")
        arguments = run_dict.get("arguments") or {}

        if not tool_name:
            continue

        action_hash = get_action_hash(tool_name, arguments)
        data_version_id = _data_version_id_from_payload(run_dict)
        key = (action_hash, data_version_id)

        if key in seen:
            continue

        seen.add(key)

        yield {
            "action_hash": action_hash,
            "data_version_id": data_version_id,
            "tool_name": tool_name,
            "arguments": arguments,
        }

    for obs in state.get("observations", []) or []:
        obs_dict = _as_dict(obs)

        if not _looks_like_real_execution_observation(obs_dict):
            continue

        tool_name = obs_dict.get("tool_name")
        arguments = obs_dict.get("arguments") or {}

        if not tool_name:
            continue

        action_hash = get_action_hash(tool_name, arguments)
        data_version_id = _data_version_id_from_payload(obs_dict)
        key = (action_hash, data_version_id)

        if key in seen:
            continue

        seen.add(key)

        yield {
            "action_hash": action_hash,
            "data_version_id": data_version_id,
            "tool_name": tool_name,
            "arguments": arguments,
        }


def iter_executed_action_hashes(state: dict) -> Iterable[str]:
    """
    Backward-compatible hash iterator for older tests/callers.
    """
    for record in iter_executed_action_records(state):
        yield record["action_hash"]


def has_duplicate_executed_action(
    *,
    state: dict,
    tool_name: str,
    arguments: dict,
) -> bool:
    current_hash = get_action_hash(tool_name, arguments or {})
    active_data_version_id = state.get("active_data_version_id")

    for record in iter_executed_action_records(state):
        if record.get("action_hash") != current_hash:
            continue

        record_version = record.get("data_version_id")

        # If both versions are known, duplicate only within the same version.
        if active_data_version_id and record_version:
            if str(record_version) == str(active_data_version_id):
                return True
            continue

        # Backward-compatible fallback for very old states without version info.
        if not active_data_version_id and not record_version:
            return True

    return False