# Contributing

Thank you for helping improve **digilab**.

## Development setup

```bash
git clone <repository-url>
cd digilab-harness
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks before opening a PR

```bash
ruff check .
ruff format --check .
mypy src/digilab
pytest
```

Optional course regression (requires paths under `course_archive/`):

```bash
python course_archive/run_all.py
```

## Adding a new 74-series chip

1. Add `src/digilab/chips/chip_<model>.py` exposing `SPEC: ChipSpec`.
2. Register the module in `_MODULES` inside `src/digilab/chips/registry.py`.
3. Add parser primitive mapping if needed (`common/parser.py`).
4. Extend `tests/test_smoke.py` (and chip self-check if applicable).
5. Document in `src/digilab/chips/CHANGELOG.md`.

Alternatively, ship a separate Python package that declares
`[project.entry-points."digilab.chips"]` pointing at a callable or module with
`SPEC`; built-in models always win on name conflicts.

## Code style

- Python 3.9+ compatible syntax.
- Ruff is the single formatter and linter (line length 100).
- Prefer small, focused commits with clear messages.
