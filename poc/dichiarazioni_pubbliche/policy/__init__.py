"""Pure editorial/legal policy modules for Dichiarazioni Pubbliche.

Every module in this package is:

* pure — no network, filesystem, database, clock, or environment access;
* deterministic — identical inputs produce identical outputs;
* importable without a database or any configured provider.

These modules encode *product* decisions. They do not encode legal conclusions.
An unresolved qualified question (see ``docs/policy/legal-closure-register.md``)
means the corresponding behaviour stays in its fail-closed safe default; it is
never "closed" by code.
"""

from __future__ import annotations

__all__ = [
    "challenge_workflow",
    "excerpt_policy",
    "intake_policy",
    "intent_policy",
    "privacy_policy",
]
