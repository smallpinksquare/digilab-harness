# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-14

First public release.  Migrated from a private course-experiment repository to an
open-source layout; no functional changes to the synthesiser or verifier.

### Added

- **Package** — `digilab` under `src/digilab/` with editable install (`pip install -e .`);
  CLI entry-point `digilab` exposing `synth`, `verify`, and `selftest` sub-commands.
- **Chip library** — built-in support for 7400, 7420, 74138 (`DECODE3`), 74153 (`MUX4`),
  74151 (`MUX8` dual-output).  Third-party chips registerable via the `digilab.chips`
  `importlib.metadata` entry-point group; built-in models win on name conflicts.
- **DSL features** — gate-level (`NAND2`, `NAND4`), high-level MSI primitives, integer
  literals (`0`/`1`), intermediate variables (CSE), multi-LHS assignments, daisy-chain
  fanout, VCC-input substitution.
- **Examples** — four runnable examples under `examples/`; validated by
  `tests/test_examples_regression.py` in CI.
- **Docs** — `docs/` with five English pages (index, architecture, DSL reference,
  physical wiring, chip extension) and a Chinese entry (`docs/zh/index.md`);
  bilingual README (`README.md` + `README.zh-CN.md`).
- **Course archive** — original course materials preserved under `course_archive/`
  with `run_all.py` / `run_all.ps1` SHA256 regression helper.
- **Quality** — Ruff lint + format, mypy strict, pytest + coverage configured in
  `pyproject.toml`; `py.typed` marker.
- **CI** — GitHub Actions on Ubuntu and Windows, Python 3.9 / 3.10 / 3.11 / 3.12 / 3.13.
- **Governance** — BSD-3-Clause `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, GitHub issue/PR templates, `.editorconfig`, `.gitattributes`
  (`course_archive/` marked `linguist-vendored`).

### Chip sub-changelog

See [`src/digilab/chips/CHANGELOG.md`](src/digilab/chips/CHANGELOG.md) for the
detailed history of individual chip additions (74138, 74153, 74151) prior to this
open-source release.

[0.1.0]: https://github.com/digilab-harness/digilab/releases/tag/v0.1.0
