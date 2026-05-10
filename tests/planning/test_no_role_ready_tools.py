from core.analysis_tool_plugins.arguments import ArgumentSchema
from core.analysis_tool_plugins.base import AnalysisToolPlugin
from core.analysis_tool_plugins.policy_types import PlanningPolicy
from core.dataset_intelligence.schemas import DatasetProfileV2
from core.planning.schemas import PlanStep
from core.planning import verifier
from core.planning.verifier import verify_plan_step


def make_profile():
    return DatasetProfileV2.model_validate({
        "dataset_name": "uploaded_dataset",
        "data_version_id": "raw_v1",
        "n_rows": 5,
        "n_cols": 3,
        "columns": {
            "GPA": {
                "name": "GPA",
                "semantic_type": "continuous_numeric",
                "raw_dtype": "float64",
                "measurement_scale": "continuous",
                "n_missing": 0,
                "missing_rate": 0.0,
                "n_unique": 5,
                "unique_rate": 1.0,
            },
            "SATM": {
                "name": "SATM",
                "semantic_type": "continuous_numeric",
                "raw_dtype": "float64",
                "measurement_scale": "continuous",
                "n_missing": 0,
                "missing_rate": 0.0,
                "n_unique": 5,
                "unique_rate": 1.0,
            },
            "Sex": {
                "name": "Sex",
                "semantic_type": "binary_categorical",
                "raw_dtype": "object",
                "measurement_scale": "nominal",
                "n_missing": 0,
                "missing_rate": 0.0,
                "n_unique": 2,
                "unique_rate": 0.4,
            },
        },
    })


def make_step(tool_name):
    return PlanStep(
        step_id=f"step_{tool_name}",
        title=tool_name,
        tool_name=tool_name,
        method_family="eda",
        status="needs_user_choice",
        execution_ready=False,
        purpose="Test no-role ready tool.",
        rationale="Test no-role ready tool.",
        variables={},
        arguments={},
        candidate_variables={},
        required_user_choices=["analysis variables"],
        warnings=[
            "Plugin has no variable role contract; cannot mark step execution-ready from planning."
        ],
    )


def test_get_summary_stats_no_role_tool_is_ready():
    step = make_step("get_summary_stats")

    verified = verify_plan_step(step, make_profile())

    assert verified.status == "ready"
    assert verified.execution_ready is True
    assert verified.required_user_choices == []
    assert not any(
        "Plugin has no variable role contract" in warning
        for warning in verified.warnings
    )


def test_inspect_dataset_policy_ready_no_role_tool_is_ready():
    step = make_step("inspect_dataset")

    verified = verify_plan_step(step, make_profile())

    assert verified.status == "ready"
    assert verified.execution_ready is True
    assert verified.required_user_choices == []
    assert not any(
        "Plugin has no variable role contract" in warning
        for warning in verified.warnings
    )


def test_missingness_report_no_role_tool_is_ready():
    step = make_step("missingness_report")

    verified = verify_plan_step(step, make_profile())

    assert verified.status == "ready"
    assert verified.execution_ready is True
    assert verified.required_user_choices == []


def test_no_role_plugin_without_ready_policy_stays_conservative(monkeypatch):
    def fake_execute(context):
        return {"status": "ok", "details": {}}

    plugin = AnalysisToolPlugin(
        tool_name="no_role_needs_choices",
        display_name="No Role Needs Choices",
        execute=fake_execute,
        argument_schema=ArgumentSchema(),
        method_family="test",
        variable_roles=[],
        planning_policy=PlanningPolicy(
            ready_without_user_variables=False,
            requires_variable_contract=True,
        ),
    )

    monkeypatch.setattr(
        verifier,
        "get_plugin",
        lambda tool_name: plugin
        if tool_name == "no_role_needs_choices"
        else None,
    )

    step = PlanStep(
        step_id="step_no_role_needs_choices",
        title="No Role Needs Choices",
        tool_name="no_role_needs_choices",
        method_family="test",
        status="ready",
        execution_ready=True,
        purpose="Test conservative no-role plugin.",
        rationale="Test conservative no-role plugin.",
        variables={},
        arguments={},
        candidate_variables={},
        required_user_choices=[],
        warnings=[],
    )

    verified = verify_plan_step(step, make_profile())

    assert verified.status == "needs_user_choice"
    assert verified.execution_ready is False
    assert "analysis variables" in verified.required_user_choices
    assert any(
        "Plugin has no variable role contract" in warning
        for warning in verified.warnings
    )


def test_get_correlation_matrix_no_role_tool_is_ready():
    step = make_step("get_correlation_matrix")

    verified = verify_plan_step(step, make_profile())

    assert verified.status == "ready"
    assert verified.execution_ready is True
    assert verified.required_user_choices == []
