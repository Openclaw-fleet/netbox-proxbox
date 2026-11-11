# Proxbox CLI Docgen

`proxbox_cli` now ships a small documentation-generation pipeline modeled after the one in `netbox-cli`.

## What It Generates

The generator writes three artifact sets under `docs/generated/`:

- `proxbox-cli-command-capture.md`: combined raw snapshot of representative command captures
- `proxbox-cli/raw/*.json`: one JSON artifact per captured command plus `index.json`
- `proxbox-cli/catalog.json`: recursively generated inventory of the CLI command tree

MkDocs then uses `docs/hooks.py` to render those raw artifacts into:

- `docs/reference/proxbox-cli/command-examples/`
- `docs/reference/proxbox-cli/command-catalog/`

## Capture Strategy

The current capture set is intentionally safe and reproducible:

- it runs `python -m proxbox_cli ...` from the local repository checkout
- it captures `--help` output for representative command groups and commands
- it generates example invocations automatically by walking the Typer/Click command tree

That means the documentation can be rebuilt without depending on a live `proxbox-api` instance.

## Regenerate

From the repository root, use the reviewed lockfile toolchain:

```bash
uv run --frozen --extra cli python docs/generate_proxbox_cli_docs.py
```

Or through the locked CLI entrypoint:

```bash
uv run --frozen --extra cli pxb docs generate-capture
```

The semantic freshness gate runs with the same locked dependencies. Typer can
change help rendering between releases (for example, 0.29 adds `<bool>` labels
to flags), so an unconstrained package install is not the canonical snapshot
environment. Runtime dependency ranges remain unchanged. Review and regenerate
the captures together when deliberately updating the renderer in `uv.lock`.

Then rebuild the docs site:

```bash
uv run --with-requirements requirements-docs.txt mkdocs build
```
