from core.ui_adapter.events import (
    UIEvent,
    apply_ui_event_to_state,
    make_approve_human_review_event,
    make_cancel_plan_event,
    make_reject_human_review_event,
    make_run_plan_event,
    make_user_message_event,
    normalize_ui_event,
)
from core.ui_adapter.snapshot import build_ui_snapshot