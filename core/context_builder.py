import os

import pandas as pd
from core.schema import ContextPackage, DatasetProfile, ColumnProfile


def get_observation_data_version(obs):
    if not isinstance(obs, dict):
        return None

    if obs.get("data_version_id"):
        return obs.get("data_version_id")

    structured = obs.get("structured_data", {})
    if isinstance(structured, dict):
        return structured.get("data_version_id")

    return None

def format_observation_history(observations, active_data_version_id=None, max_items=20):
    lines = []

    for obs in (observations or [])[-max_items:]:
        if not isinstance(obs, dict):
            continue

        tool_name = obs.get("tool_name", "unknown_tool")
        status = obs.get("status", "unknown")
        success = obs.get("success")
        message = obs.get("message", "")
        summary = obs.get("summary", "")
        obs_version = get_observation_data_version(obs)

        if active_data_version_id and obs_version:
            if obs_version == active_data_version_id:
                version_status = "CURRENT"
            else:
                version_status = "STALE"
        else:
            version_status = "UNKNOWN_VERSION"

        lines.append(
            f"- tool={tool_name}, status={status}, success={success}, "
            f"data_version_id={obs_version}, version_status={version_status}, "
            f"message={message}, summary={summary}"
        )

        # 关键：只有 CURRENT observation 才允许暴露 payload
        if version_status == "CURRENT":
            structured = obs.get("structured_data", {})
            payload = structured.get("payload") if isinstance(structured, dict) else None

            if payload:
                lines.append(f"  payload={payload}")

        elif version_status == "STALE":
            lines.append(
                "  NOTE: This observation was computed on an older data version. "
                "Do not use it for current numeric answers."
            )

    return "\n".join(lines) if lines else "No previous observations."


def _format_deliverable_gate_item(item):
    if isinstance(item, str):
        return f"- {item}\n"

    if not isinstance(item, dict):
        return f"- {item}\n"

    lines = []

    for key in [
        "deliverable_id",
        "description",
        "reason",
        "satisfied_by",
        "required_evidence",
        "missing_evidence",
    ]:
        value = item.get(key)

        if value not in (None, "", [], {}):
            lines.append(f"  {key}: {value}")

    if not lines:
        return f"- {item}\n"

    return "- " + "\n".join(lines).lstrip() + "\n"


def format_deliverable_gate_feedback(deliverable_check):
    if not deliverable_check:
        return ""

    if not isinstance(deliverable_check, dict):
        deliverable_check = {
            "status": getattr(deliverable_check, "status", None),
            "message": getattr(deliverable_check, "message", None),
            "satisfied": getattr(deliverable_check, "satisfied", []),
            "missing": getattr(deliverable_check, "missing", []),
            "blocked": getattr(deliverable_check, "blocked", []),
        }

    deliverable_log = "Deliverable Gate Feedback:\n"
    deliverable_log += f"- status: {deliverable_check.get('status')}\n"
    deliverable_log += f"- message: {deliverable_check.get('message')}\n"

    satisfied = deliverable_check.get("satisfied", []) or []
    if satisfied:
        deliverable_log += "\nSatisfied deliverables/evidence:\n"
        for item in satisfied:
            deliverable_log += _format_deliverable_gate_item(item)

    missing = deliverable_check.get("missing", []) or []
    if missing:
        deliverable_log += "\nMissing deliverables/evidence:\n"
        for item in missing:
            deliverable_log += _format_deliverable_gate_item(item)

    blocked = deliverable_check.get("blocked", []) or []
    if blocked:
        deliverable_log += "\nBlocked deliverables/evidence:\n"
        for item in blocked:
            deliverable_log += _format_deliverable_gate_item(item)

    if deliverable_check.get("status") in {"needs_more_work", "missing", "blocked"}:
        deliverable_log += (
            "\nCRITICAL: A previous final_answer was blocked by the DeliverableGate. "
            "Do not produce final_answer yet. Call the tools needed to satisfy the missing deliverables/evidence, "
            "unless the missing item is truly unrecoverable.\n"
        )

    return deliverable_log


def _as_mapping(value):
    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    return {}


def format_task_contract_summary(task_contract):
    contract = _as_mapping(task_contract)

    if not contract:
        return ""

    lines = ["Task Contract:"]

    for key in ["contract_id", "user_goal", "status"]:
        value = contract.get(key)

        if value not in (None, "", [], {}):
            lines.append(f"- {key}: {value}")

    deliverables = contract.get("required_deliverables", []) or []

    if deliverables:
        lines.append("\nRequired deliverables:")

        for item in deliverables:
            if isinstance(item, str):
                lines.append(f"- deliverable_id: {item}")
                continue

            deliverable = _as_mapping(item)

            if not deliverable:
                lines.append(f"- {item}")
                continue

            deliverable_id = deliverable.get("deliverable_id", "unknown")
            lines.append(f"- deliverable_id: {deliverable_id}")

            for key in ["description", "status", "satisfied_by", "required_evidence"]:
                value = deliverable.get(key)

                if value not in (None, "", [], {}):
                    lines.append(f"  {key}: {value}")

    constraints = contract.get("constraints", []) or []

    if constraints:
        lines.append("\nConstraints:")

        for item in constraints:
            constraint = _as_mapping(item)

            if not constraint:
                lines.append(f"- {item}")
                continue

            constraint_id = constraint.get("constraint_id", "unknown")
            description = constraint.get("description", "")
            constraint_type = constraint.get("type", "other")
            lines.append(
                f"- constraint_id: {constraint_id}, type: {constraint_type}, "
                f"description: {description}"
            )

    lines.append(
        "\nPreserve this task_contract unless the user changes the task. "
        "Use it to choose the next missing tool/evidence before final_answer."
    )

    return "\n".join(lines)


def generate_profile(file_path: str) -> DatasetProfile:
    """Build a dataset profile report (multiple formats supported)."""

    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == '.csv':
            df = pd.read_csv(file_path)
        elif ext in ['.xls', '.xlsx']:
            df = pd.read_excel(file_path)
        elif ext == '.parquet':
            df = pd.read_parquet(file_path, engine='pyarrow')
        else:
            raise ValueError(f"Unsupported profile format: {ext}")

        def _infer_semantic_type(s: pd.Series) -> str:
            if pd.api.types.is_bool_dtype(s):
                return "boolean"
            if pd.api.types.is_numeric_dtype(s):
                return "numeric"
            if pd.api.types.is_datetime64_any_dtype(s):
                return "datetime"
            if pd.api.types.is_categorical_dtype(s):
                return "categorical"
            if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
                non_missing = s.dropna()
                if len(non_missing) == 0:
                    return "unknown"
                numeric_rate = pd.to_numeric(non_missing, errors="coerce").notna().mean()
                if numeric_rate >= 0.85:
                    return "numeric_like"
                if non_missing.nunique() <= max(20, int(0.2 * len(s))):
                    return "categorical"
                return "text"
            return "unknown"

        def _is_id_like(col_name: str, s: pd.Series) -> bool:
            name = str(col_name).lower()
            n = len(s)
            if n == 0:
                return False
            unique_rate = s.nunique(dropna=True) / max(n, 1)
            return (
                    name in {"id", "uid", "uuid", "student_id", "record_id"}
                    or name.endswith("_id")
                    or (unique_rate > 0.95 and s.nunique(dropna=True) > 20)
            )

        columns_info = {}
        n_rows = len(df)

        for col, dtype in df.dtypes.items():
            s = df[col]
            n_missing = int(s.isnull().sum())
            n_unique = int(s.nunique(dropna=True))
            semantic_type = _infer_semantic_type(s)

            columns_info[str(col)] = {
                "name": str(col),
                "dtype": str(dtype),
                "n_missing": n_missing,
                "missing_rate": float(n_missing / max(n_rows, 1)),
                "n_unique": n_unique,
                "semantic_type": semantic_type,
                "is_numeric_like": semantic_type in {"numeric", "numeric_like"},
                "is_id_like": _is_id_like(str(col), s),
            }

        profile_dict = {
            "dataset_name": os.path.basename(file_path),
            "n_rows": int(len(df)),
            "n_cols": int(len(df.columns)),
            "columns": columns_info,
        }

        return DatasetProfile(**profile_dict)

    except Exception as e:
        print(f"Profile generation failed: {str(e)}")
        raise e


def build_context(step,
                  max_steps,
                  user_request,
                  profile,
                  observations,
                  workspace_dir="./",
                  deliverable_check=None,
                  task_contract=None,
                  data_versions=None,
                  active_data_version_id=None,
                  data_audit_log=None,
                  ):
    """
    Build the full context text sent to the LLM.
    """

    if isinstance(profile, dict):
        rows = profile.get("n_rows", "unknown")
        cols_dict = profile.get("columns", {})
        cols = list(cols_dict.keys()) if isinstance(cols_dict, dict) else ["unable to parse column names"]
    else:
        rows = getattr(profile, "n_rows", "unknown")
        cols = list(getattr(profile, "columns", {}).keys())

    history_log = format_observation_history(
        observations=observations,
        active_data_version_id=active_data_version_id,
    )

    for idx, obs in enumerate(observations):
        if isinstance(obs, dict):
            t_name = obs.get("tool_name", "unknown_tool")
            status = obs.get("status") or obs.get("structured_data", {}).get("status", "unknown")
            success = obs.get("success") if "success" in obs else obs.get("structured_data", {}).get("success")
            error_code = obs.get("error_code") or obs.get("structured_data", {}).get("error_code")
            message = obs.get("message") or obs.get("summary", "")
            artifacts = obs.get("artifacts") or obs.get("structured_data", {}).get("artifacts", [])

            marker = "✅" if status in ["ok", "warning"] else "❌"
            history_log += (
                f"{marker} [step {idx + 1}] tool: {t_name}\n"
                f"- status: {status}\n"
                f"- success: {success}\n"
            )

            if error_code:
                history_log += f"- error_code: {error_code}\n"

            if message:
                history_log += f"- message: {str(message)[:500]}\n"

            if artifacts:
                history_log += f"- artifacts: {artifacts}\n"

            payload = obs.get("structured_data", {}).get("payload")
            if payload:
                history_log += f"- key payload: {str(payload)[:800]}\n"

            history_log += "\n"

    if not history_log:
        history_log = "No prior executions. This is the first step—choose the first tool to call."

    task_contract_log = format_task_contract_summary(task_contract)
    deliverable_log = format_deliverable_gate_feedback(deliverable_check)

    data_version_log = ""

    if active_data_version_id:
        data_version_log += "\n### Active Data Version\n"
        data_version_log += f"- active_data_version_id: {active_data_version_id}\n"

        active_version = None
        for v in data_versions or []:
            if v.get("version_id") == active_data_version_id:
                active_version = v
                break

        if active_version:
            data_version_log += f"- rows: {active_version.get('n_rows')}\n"
            data_version_log += f"- columns: {active_version.get('n_cols')}\n"
            data_version_log += f"- operation: {active_version.get('operation')}\n"
            data_version_log += f"- parent_version_id: {active_version.get('parent_version_id')}\n"

    context_text = (
        f"User request:\n{user_request}\n\n"
        f"Dataset overview:\n- rows: {rows}\n- columns: {cols}\n\n"
        f"{data_version_log}\n"
        f"{task_contract_log}\n\n"
        f"History of actions and results:\n{history_log}\n\n"
        "Evidence reuse policy:\n"
        "- A previous observation may be reused for a numeric answer only if its "
        "data_version_id equals the current active_data_version_id.\n"
        "- Observations marked STALE must not be used to answer current numeric questions.\n"
        "- If the needed result is only available from a stale observation, call the appropriate tool again.\n\n"
        f"History of actions and results:\n{history_log}\n\n"
        f"{deliverable_log}\n"
        f"Read the history carefully. Do not repeat successful tools with the same intent. "
        f"If you see a Deliverable Gate warning, satisfy the missing deliverables before final_answer. "
        f"If you see an intervention warning, change strategy or output final_answer."
    )

    return ContextPackage(
        step=step,
        max_steps=max_steps,
        user_request=user_request,
        context_text=context_text,
        profile=profile,
        observations=observations,
        workspace_dir=workspace_dir,
        deliverable_check=deliverable_check,

        data_versions=data_versions or [],
        active_data_version_id=active_data_version_id,
        data_audit_log=data_audit_log or [],

    )
