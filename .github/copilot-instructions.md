# tdl_export — Project Guidelines

## Architecture

`tdl_export` is a Python CLI wrapper around the external [`tdl`](https://github.com/iyear/tdl) tool that automates Telegram media export and resumable downloading.

**Component boundaries:**

- `src/tdl_export/cli.py` — Core logic: Pydantic models, JSON state management, and the `download_media()` workflow
- `data/<group_id>.json` — Persisted chat export state (tracks message metadata and download status)
- `downloads/<group_id>/` — Destination for downloaded media files
- `scripts/gen_docs.py` — Fire-based doc generator (processes `.py` and `.ipynb` files)

**Workflow:** load JSON state → `tdl chat export` → merge/deduplicate messages → scan local files → `tdl dl` new media → persist updated state.

## Build and Test

```bash
uv sync                  # Install all dependencies (use uv, not pip/poetry)
uv sync --group test     # Include test dependencies

make test                # Run pytest with coverage (threshold: 80%)
make format              # Run pre-commit hooks (Ruff lint + format)

uv run tdl_export        # Run the CLI
```

**Poethepoet shortcuts:**

```bash
uv run poe cli           # Run CLI
uv run poe docs          # Generate + serve docs
```

## Conventions

- **Package manager:** Always use `uv` — never `pip install` or `poetry`
- **Linting/formatting:** Ruff (via `make format` or pre-commit); do not run `black` or `flake8`
- **Data models:** Pydantic v2 `BaseModel` for all structured data
- **Terminal output:** Use `rich` for console output; avoid plain `print()` in production code
- **Type checking:** `ty` (Astral's type checker, not `mypy`)
- **Tests:** `pytest` with `pytest-asyncio` for async; mark slow tests with `@pytest.mark.slow`; CI skips tests if none exist

## Potential Pitfalls

- **`tdl` is an external binary**: Must be installed and authenticated (`tdl login`) before running. It is not a Python dependency.
- **`group_id` is hardcoded** in `main()` inside `cli.py` — modify it there before running.
- **No tests yet**: The `tests/` directory is empty. CI gracefully skips pytest if no test files exist.
- **Docker**: No `ENTRYPOINT`/`CMD` in `docker/Dockerfile` — specify the command at runtime.
