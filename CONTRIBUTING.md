# Contributing

Thanks for contributing to token-auditor.

## Development setup

```bash
uv sync --group dev
```

Run the same checks used by CI before opening a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check .
uv run pytest -v
```

Keep pull requests focused, include tests for behavior changes, and update the
README when the public CLI or output contract changes. Do not commit session
logs, prompts, credentials, or other potentially sensitive local data.

## Pull requests

Open a pull request against `main` with a clear description of the motivation,
the behavior change, and validation performed. Maintainers may request changes
before merging.

## Releases

Merging a pull request into `main` creates a GitHub Release automatically. The
release version uses the UTC date (`YYYY.MM.DD`); additional releases on the
same date use a PEP 440 post-release suffix (`YYYY.MM.DD.post1`, then
`YYYY.MM.DD.post2`, and so on).
