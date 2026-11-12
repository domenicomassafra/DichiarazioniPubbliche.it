"""Static payload fixture that carries its own build provenance (DP-481)."""

from __future__ import annotations

from pathlib import Path

from tools.dp481_static_contract import write_build_stamp

HOME = (b'<html><head><link rel="icon" href="/favicon.svg"></head>'
        b'<body><main><h1>Safe static page</h1></main></body></html>')
ROUTES = ("esplora", "metodo", "correzioni", "dati", "progetto",
          "accedi", "account", "privacy", "segnalazioni")


def build_static_payload(static: Path, git_sha: str, projection_index: Path) -> None:
    """Write the minimal valid static bundle plus the stamp its build would emit."""
    (static / "index.html").write_bytes(HOME)
    for route in ROUTES:
        destination = static / route / "index.html"
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(HOME)
    (static / "favicon.svg").write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    (static / "robots.txt").write_text("User-agent: *\nDisallow: /account/\n")
    (static / "sitemap.xml").write_text("<urlset/>")
    write_build_stamp(static, git_sha=git_sha, projection_index=projection_index)
