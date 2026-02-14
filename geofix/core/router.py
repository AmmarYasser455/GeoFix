"""Intelligent model router — selects the optimal LLM based on query complexity.

Routes queries through a lightweight heuristic classifier:
  Simple  → fast model  (Llama 3.2)
  Medium  → balanced    (Llama 3.1 8B)
  Complex → deep        (DeepSeek R1)
"""

from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger("geofix.core.router")

_SIMPLE_PATTERNS = [
    r"^(hi|hello|hey|yo|sup|greetings|thanks|thank you|bye|goodbye)",
    r"^what is .{0,30}$",
    r"^define .{0,30}$",
    r"^(yes|no|ok|okay|sure|got it|understood)$",
]

_COMPLEX_PATTERNS = [
    r"(compare|analyze|evaluate|trade-?off|pros and cons)",
    r"(write|generate|create) .*(script|code|function|program)",
    r"(debug|fix|refactor|optimize) .*(code|script|function)",
    r"(explain .*(algorithm|architecture|system|design))",
    r"(step[- ]by[- ]step|detailed|comprehensive|thorough)",
    r"(multi-?step|chain of thought|reasoning)",
]


class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


from geofix.core.config import DEFAULT_CONFIG


def classify_complexity(query: str, history_len: int = 0) -> Complexity:
    """Classify query complexity using pattern matching and heuristics."""
    text = query.strip().lower()
    word_count = len(text.split())

    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, text):
            return Complexity.SIMPLE

    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, text):
            return Complexity.COMPLEX

    if word_count >= 50 or history_len >= 10:
        return Complexity.COMPLEX
    if word_count <= 5:
        return Complexity.SIMPLE

    return Complexity.MEDIUM


def select_model(
    query: str,
    history_len: int = 0,
    user_override: str | None = None,
) -> str:
    """Select the best model for a query.

    If user has manually selected a model via settings, that takes priority.
    """
    if user_override:
        return user_override

    complexity = classify_complexity(query, history_len)

    if complexity == Complexity.SIMPLE:
        model = DEFAULT_CONFIG.router.simple_model
    elif complexity == Complexity.MEDIUM:
        model = DEFAULT_CONFIG.router.medium_model
    else:
        model = DEFAULT_CONFIG.router.complex_model

    logger.info("Router: %s → %s (%s)", query[:40], model, complexity.value)
    return model
