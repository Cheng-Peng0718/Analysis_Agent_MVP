import pytest

from core.app_backend.session import (
    build_graph_config,
    create_app_session,
    make_session_id,
    normalize_session_id,
)


def test_make_session_id_has_prefix():
    session_id = make_session_id()

    assert session_id.startswith("session_")
    assert len(session_id) > len("session_")


def test_normalize_session_id_makes_path_safe():
    assert normalize_session_id(" user session / 1 ") == "user_session_1"


def test_normalize_session_id_rejects_empty_values():
    with pytest.raises(ValueError):
        normalize_session_id("   ")


def test_build_graph_config_uses_normalized_thread_id():
    config = build_graph_config(" user session / 1 ")

    assert config == {
        "configurable": {
            "thread_id": "user_session_1",
        }
    }


def test_create_app_session_creates_workspace_and_config(tmp_path):
    session = create_app_session(
        workspace_root=str(tmp_path),
        session_id="my session",
    )

    assert session.session_id == "my_session"
    assert session.graph_config == {
        "configurable": {
            "thread_id": "my_session",
        }
    }

    assert session.to_dict()["session_id"] == "my_session"
    assert session.to_dict()["workspace_dir"] == session.workspace_dir
    assert (tmp_path / "my_session").exists()