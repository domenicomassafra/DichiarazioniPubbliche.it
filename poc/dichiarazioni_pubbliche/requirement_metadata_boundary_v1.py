"""Safe immutable metadata capture for private DP-314 planning and preflight.

A frozen dataclass may still contain a subclass of str whose __deepcopy__
changes approval, source identity or date during dataclasses.asdict.
"""
from dataclasses import fields


def canonical_requirement_metadata(record: object, expected_type: type, error: str):
    """Reject custom fields before constructing a detached exact-typed record."""
    if type(record) is not expected_type:
        raise ValueError(error)
    values = {}
    for field in fields(expected_type):
        value = getattr(record, field.name)
        if type(value) is not str and not (
            field.name == "jurisdiction_ref" and value is None
        ):
            raise ValueError(error)
        values[field.name] = value
    return expected_type(**values)
