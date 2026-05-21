"""Status rules for the buffer index."""
from __future__ import annotations

import math

DEFAULT_CRITICAL_THRESHOLD = 0.70
DEFAULT_NORMAL_THRESHOLD = 1.00
DEFAULT_SURPLUS_THRESHOLD = 1.50


def define_status(
    ibuf: float,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    normal_threshold: float = DEFAULT_NORMAL_THRESHOLD,
    surplus_threshold: float = DEFAULT_SURPLUS_THRESHOLD,
) -> str:
    """Define business status by buffer coverage index."""
    if ibuf is None or not math.isfinite(ibuf):
        return "Не рассчитано"
    if ibuf <= critical_threshold:
        return "Критическое отклонение"
    if ibuf <= normal_threshold:
        return "Предупреждение"
    if ibuf <= surplus_threshold:
        return "Норма"
    return "Избыточный буфер"


STATUS_COLORS = {
    "Критическое отклонение": "rgba(248, 113, 113, 0.32)",
    "Предупреждение": "rgba(251, 191, 36, 0.32)",
    "Норма": "rgba(74, 222, 128, 0.28)",
    "Избыточный буфер": "rgba(96, 165, 250, 0.27)",
    "Не рассчитано": "rgba(148, 163, 184, 0.18)",
}

STATUS_HEX = {
    "Критическое отклонение": "#f87171",
    "Предупреждение": "#fbbf24",
    "Норма": "#4ade80",
    "Избыточный буфер": "#60a5fa",
    "Не рассчитано": "#94a3b8",
}

STATUS_ORDER = [
    "Критическое отклонение",
    "Предупреждение",
    "Норма",
    "Избыточный буфер",
    "Не рассчитано",
]
