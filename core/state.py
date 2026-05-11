import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional
from core.schema import ActionProposal, DatasetProfile, ToolExecutionResult, VerificationResult


class GraphState(TypedDict):
    user_request: str
    workspace_dir: str

    dataset_profile: Any
    dataset_profile_v2: dict
    dataset_summary: dict
    capability_map: dict

    observations: Annotated[list, operator.add]
    analysis_runs: Annotated[list, operator.add]

    current_action: Any
    current_execution: Any
    current_verification: Any
    current_step: int
    max_steps: int

    task_contract: Optional[Dict[str, Any]]
    deliverable_check: Optional[Dict[str, Any]]
    deliverable_gate_attempts: int

    data_versions: Optional[List[Dict[str, Any]]]
    active_data_version_id: Optional[str]
    data_audit_log: Optional[List[Dict[str, Any]]]

    interaction_intent: Optional[str]
    intent_decision: dict
    task_spec: dict
    backend_command: Optional[str]

    pending_plan: Optional[Dict[str, Any]]
    plan_status: Optional[str]
    plan_execution_status: Optional[str]
    current_plan_step_id: Optional[str]
    action_origin: Optional[str]
    pending_plan_clarification: Optional[Dict[str, Any]]

    final_answer: Optional[str]
    assistant_response: dict

    execution_audit: dict
    repair_decision: dict
    repair_attempts: list
    repair_proposal: dict
    state_serialization_audit: dict

    latest_ui_event: dict
    human_review_required: bool
    pending_action: Any
    human_review_action_hash: Optional[str]
    human_review_rejection_reason: Optional[str]
    human_review_decision: Optional[str]
