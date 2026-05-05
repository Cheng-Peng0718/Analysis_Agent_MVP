from typing import Any, Dict, List, Optional

from core.analysis_tool_plugins import get_plugin as get_unified_plugin


def _build_legacy_analysis_run_from_observation(
    *,
    tool_name: str,
    action_id: str,
    arguments: Dict[str, Any],
    data_version_id: Optional[str],
    status: str,
    success: bool,
    message: Optional[str],
    payload: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    observation_id: str,
) -> Dict[str, Any]:
    """
    Legacy fallback.

    During migration, some tools still only have old analysis_plugins.
    Once all tools are migrated to core.analysis_tool_plugins, this fallback
    and core.analysis_plugins can be removed.
    """
    from core.analysis_plugins import get_plugin as get_legacy_plugin

    legacy_plugin = get_legacy_plugin(tool_name)

    return legacy_plugin.build_analysis_run(
        action_id=action_id,
        arguments=arguments or {},
        data_version_id=data_version_id,
        status=status,
        success=success,
        message=message,
        payload=payload or {},
        artifacts=artifacts or [],
        observation_id=observation_id,
    )


def build_analysis_run_from_observation(
    *,
    tool_name: str,
    action_id: str,
    arguments: Dict[str, Any],
    data_version_id: Optional[str],
    status: str,
    success: bool,
    message: Optional[str],
    payload: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    observation_id: str,
) -> Dict[str, Any]:
    """
    Convert one tool observation into a UI-friendly AnalysisRun.

    Migration priority:
    1. Unified AnalysisToolPlugin
    2. Legacy core.analysis_plugins fallback
    """
    unified_plugin = get_unified_plugin(tool_name)

    if unified_plugin is not None:
        return unified_plugin.build_analysis_run(
            action_id=action_id,
            arguments=arguments or {},
            data_version_id=data_version_id,
            status=status,
            success=success,
            message=message,
            payload=payload or {},
            artifacts=artifacts or [],
            observation_id=observation_id,
        )

    return _build_legacy_analysis_run_from_observation(
        tool_name=tool_name,
        action_id=action_id,
        arguments=arguments or {},
        data_version_id=data_version_id,
        status=status,
        success=success,
        message=message,
        payload=payload or {},
        artifacts=artifacts or [],
        observation_id=observation_id,
    )