from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _python_files():
    for path in PROJECT_ROOT.rglob("*.py"):
        if any(part in path.parts for part in {".git", ".venv", "venv", "__pycache__"}):
            continue
        yield path


def test_task_contract_has_one_canonical_definition():
    target = "class " + "TaskContract"
    definitions = []

    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if target in text:
            definitions.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert definitions == ["core/domain/deliverable.py"]


def test_schema_reexports_canonical_task_contract():
    from core.domain.deliverable import TaskContract as DomainTaskContract
    from core.schema import TaskContract as SchemaTaskContract

    assert SchemaTaskContract is DomainTaskContract


def test_deliverable_gate_contract_is_not_named_task_contract():
    text = (PROJECT_ROOT / "core/deliverables/contracts.py").read_text(
        encoding="utf-8",
    )

    assert "class DeliverableGateContract" in text
    assert "class " + "TaskContract" not in text


def test_domain_contracts_do_not_import_frameworks_or_ui():
    forbidden = {
        "langgraph",
        "streamlit",
        "core.ui_adapter",
        "ui.",
    }

    for path in (PROJECT_ROOT / "core/domain").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        violations = [term for term in forbidden if term in text]
        assert not violations, f"{path} imports forbidden boundary terms: {violations}"
