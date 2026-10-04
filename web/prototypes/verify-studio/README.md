# Verify Studio prototype

These Astro screens are preserved as an operator/private-surface prototype. They are
intentionally stored outside `src/pages`, so a normal static public build cannot expose
them without authentication.

`PRODUCT.md` defines Verify Studio as private. Moving these files back under
`src/pages` is not a deployment mechanism: a future operator deployment must add an
authenticated private runtime or an equivalent access-control boundary first.
