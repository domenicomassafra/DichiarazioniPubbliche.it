"""Exact, bounded private metadata for DP-516 planner and checkpoint inputs."""

from dataclasses import fields
from datetime import datetime
from decimal import Decimal


def exact_private_metadata(value: object, records: tuple[type, ...]) -> bool:
    """Refuse dataclass/primitive subclasses before invoking their field hooks.

    Only immutable, fixed-size built-in leaves and explicitly named record
    classes can cross this private planning boundary.
    """
    allowed_leaf = (str, int, bool, Decimal, datetime, type(None))

    def inspect(current: object, depth: int = 0) -> bool:
        if depth > 4:
            return False
        actual = type(current)
        if actual in allowed_leaf:
            return True
        if actual is tuple:
            return len(current) <= 8 and all(
                inspect(item, depth + 1) for item in current
            )
        if actual in records:
            return all(
                inspect(getattr(current, field.name), depth + 1)
                for field in fields(actual)
            )
        return False

    return inspect(value)
