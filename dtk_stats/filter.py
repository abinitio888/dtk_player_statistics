from typing import List

from dtk_stats.config import DateRange
from dtk_stats.models import Match

_BYE_OPPONENTS = {"bye", "friplats"}


def filter_by_period(matches: List[Match], period: DateRange) -> List[Match]:
    return [m for m in matches if period.from_date <= m.date <= period.to_date]


def filter_byes(matches: List[Match]) -> List[Match]:
    return [m for m in matches if m.opponent.strip().lower() not in _BYE_OPPONENTS]
