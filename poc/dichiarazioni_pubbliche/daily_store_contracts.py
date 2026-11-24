"""Shared DP-638 persistence vocabulary."""

STATEMENT_STATUSES = frozenset({
    "CANDIDATE",
    "HELD_NO_SPEAKER",
    "HELD_NO_VERDICT",
    "HELD_DUPLICATE",
})
CLAIM_NATURES = frozenset({"FACTUAL", "OPINION"})
FACTUAL_VERDICTS = frozenset({
    "TRUE",
    "MOSTLY_TRUE",
    "MISLEADING",
    "FALSE",
    "NOT_VERIFIABLE",
    "CONTRADICTORY_WITH_ITSELF",
})
