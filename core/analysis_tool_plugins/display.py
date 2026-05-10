from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.analysis_tool_plugins.types import DisplayFormatter


def humanize_key(key: Any) -> str:
    if key is None:
        return ""

    text = str(key).strip()
    if not text:
        return ""

    if text.isupper():
        return text

    text = text.replace("_", " ").replace("-", " ")
    text = " ".join(text.split())

    return text[:1].upper() + text[1:]


def compact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in (d or {}).items() if v is not None}


def safe_join_list(values: Any, sep: str = " + ") -> str:
    if isinstance(values, list):
        return sep.join(str(x) for x in values)
    if isinstance(values, str):
        return values
    return ""


def clean_metric_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return value


def format_number(value: Any, digits: int = 4) -> Any:
    try:
        v = float(value)
    except Exception:
        return value

    if abs(v) < 1e-10:
        return "0"

    if abs(v) < 0.0001:
        return f"{v:.2e}"

    return f"{v:.{digits}f}".rstrip("0").rstrip(".")


def format_p_value(value: Any) -> str:
    try:
        v = float(value)
    except Exception:
        return str(value)

    if v < 0.0001:
        return "<0.0001"

    return f"{v:.4f}".rstrip("0").rstrip(".")


def format_bool_yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def format_list_semicolon(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(x) for x in value)
    return str(value)


@dataclass
class MetricDisplayConfig:
    labels: Dict[str, str] = field(default_factory=dict)
    formatters: Dict[str, DisplayFormatter] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)


@dataclass
class TableDisplayConfig:
    column_labels: Dict[str, str] = field(default_factory=dict)
    column_formatters: Dict[str, DisplayFormatter] = field(default_factory=dict)
    column_order: List[str] = field(default_factory=list)
    value_mappers: Dict[str, Dict[Any, Any]] = field(default_factory=dict)


@dataclass
class DisplayConfig:
    metrics: MetricDisplayConfig = field(default_factory=MetricDisplayConfig)
    tables: Dict[str, TableDisplayConfig] = field(default_factory=dict)
