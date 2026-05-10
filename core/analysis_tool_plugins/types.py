from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple


ExecuteFn = Callable[..., Dict[str, Any]]
ExtractorFn = Callable[
    ...,
    Tuple[str, str, Dict[str, Any], Dict[str, Any], Dict[str, Any]],
]
GuardrailFn = Callable[[Dict[str, Any]], List[Dict[str, Any]]]
DisplayFormatter = Callable[[Any], Any]
