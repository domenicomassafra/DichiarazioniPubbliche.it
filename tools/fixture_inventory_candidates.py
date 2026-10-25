"""Single source of truth for tracked data/fixture/visual asset discovery (DP-603)."""

CANDIDATE_PREFIXES = (
    "data/public/", "poc/content/", "poc/fixtures/", "poc/benchmarks/",
    "research/results/", "research/content-audits/", "research/source-candidates/",
    "tests/fixtures/", "web/src/data/", "docs/ux/prototypes-v3/generated/",
    "docs/ux/prototypes-v3/generated-style-02/", "docs/ux/reference/",
)
CANDIDATE_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".otf",
)


def is_candidate(path: str) -> bool:
    if path.endswith(CANDIDATE_SUFFIXES):
        return (path.startswith(CANDIDATE_PREFIXES)
                or path.startswith("docs/ux/") or path.startswith("web/"))
    return path.startswith(CANDIDATE_PREFIXES)
