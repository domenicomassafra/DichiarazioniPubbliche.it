# Bundled font license notices

The web build uses three pinned Fontsource packages:

- `@fontsource-variable/ibm-plex-sans@5.3.0`;
- `@fontsource-variable/newsreader@5.3.0`;
- `@fontsource/ibm-plex-mono@5.3.0`.

Their upstream package license files are vendored verbatim in this directory as
distribution notices. Each package declares `OFL-1.1` in `package-lock.json`.
The font binaries themselves continue to come from the pinned npm dependencies;
this directory contains license text only.

The local public search adapter also uses `minisearch@7.2.0` under MIT:
`MiniSearch-MIT-7.2.0.txt` retains the donor notice and
`MiniSearch-provenance.md` records its upstream tag, commit and offline benchmarks.
