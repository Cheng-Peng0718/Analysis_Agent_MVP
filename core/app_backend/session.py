from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_WORKSPACE_ROOT = "workspaces/app_sessions"


def make_session_id(prefix: str = "session") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def normalize_session_id(session_id: str) -> str:
    """
    Normalize a session id for safe workspace path usage.

    This is not user identity. It is only a backend session/workspace key.
    """
    raw = str(session_id or "").strip()

    if not raw:
        raise ValueError("session_id must not be empty.")

    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-")

    if not normalized:
        raise ValueError("session_id must contain at least one safe character.")

    return normalized


def build_graph_config(session_id: str) -> Dict[str, Any]:
    """
    Build LangGraph config for a backend session.

    UI code should pass this config into run_user_turn() and
    run_pending_plan_until_pause().
    """
    normalized = normalize_session_id(session_id)

    return {
        "configurable": {
            "thread_id": normalized,
        }
    }


@dataclass(frozen=True)
class AppSession:
    session_id: str
    workspace_dir: str
    graph_config: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_dir": self.workspace_dir,
            "graph_config": dict(self.graph_config),
        }


def create_app_session(
    *,
    workspace_root: str = DEFAULT_WORKSPACE_ROOT,
    session_id: Optional[str] = None,
) -> AppSession:
    """
    Create a backend app session.

    This function does not initialize a dataset and does not invoke LangGraph.
    It only creates the workspace/session boundary that upload and turn
    contracts can use.
    """
    safe_session_id = normalize_session_id(session_id or make_session_id())

    root = Path(workspace_root)
    workspace_dir = root / safe_session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)

    return AppSession(
        session_id=safe_session_id,
        workspace_dir=str(workspace_dir),
        graph_config=build_graph_config(safe_session_id),
    )