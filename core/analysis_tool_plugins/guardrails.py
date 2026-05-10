from __future__ import annotations

import uuid
from typing import Any, Dict, List


def evaluate_guardrails_for_plugin(plugin: Any, analysis_run: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    for evaluator in getattr(plugin, "guardrail_evaluators", []) or []:
        try:
            findings.extend(evaluator(analysis_run) or [])
        except Exception as e:
            findings.append({
                "finding_id": f"gr_{uuid.uuid4().hex[:8]}",
                "category": "guardrail_execution",
                "severity": "warning",
                "title": "Guardrail evaluator failed",
                "message": f"A guardrail evaluator failed for tool `{plugin.tool_name}`.",
                "evidence": {
                    "error": str(e),
                    "evaluator": getattr(evaluator, "__name__", str(evaluator)),
                },
                "recommendation": "Inspect the guardrail evaluator implementation.",
            })

    return findings
