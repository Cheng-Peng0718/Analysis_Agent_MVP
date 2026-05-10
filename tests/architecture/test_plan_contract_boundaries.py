from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _production_python_files():
    for path in (PROJECT_ROOT / "core").rglob("*.py"):
        if any(part in path.parts for part in {"__pycache__"}):
            continue
        yield path


def test_planning_schema_reexports_domain_plan_contracts():
    from core.domain.plan import PlanProposal as DomainPlanProposal
    from core.domain.plan import PlanStep as DomainPlanStep
    from core.planning.schemas import PlanProposal as LegacyPlanProposal
    from core.planning.schemas import PlanStep as LegacyPlanStep

    assert LegacyPlanProposal is DomainPlanProposal
    assert LegacyPlanStep is DomainPlanStep


def test_planning_schema_file_has_no_plan_class_definitions():
    text = (PROJECT_ROOT / "core/planning/schemas.py").read_text(
        encoding="utf-8",
    )

    assert re.search(r"^class\s+PlanProposal\b", text, re.MULTILINE) is None
    assert re.search(r"^class\s+PlanStep\b", text, re.MULTILINE) is None


def test_domain_plan_is_only_production_plan_contract_definition():
    targets = {
        "class " + "PlanProposal": [],
        "class " + "PlanStep": [],
    }

    for path in _production_python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")

        for target, definitions in targets.items():
            class_name = target.removeprefix("class ")
            pattern = rf"^class\s+{re.escape(class_name)}\b"

            if re.search(pattern, text, re.MULTILINE):
                definitions.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert targets["class " + "PlanProposal"] == ["core/domain/plan.py"]
    assert targets["class " + "PlanStep"] == ["core/domain/plan.py"]
