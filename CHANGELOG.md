# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-14

### Added

- Initial open-source layout: `digilab` package under `src/digilab/`, CLI
  `digilab` (`synth`, `verify`, `selftest`).
- Course materials preserved under `course_archive/` with `run_all.py` /
  `run_all.ps1` regression helper.
- Ruff, mypy (strict), pytest, and coverage configuration in `pyproject.toml`.
- Optional third-party chips via `importlib.metadata` entry-point group
  `digilab.chips` (built-in models win on name conflicts).
- `LICENSE` (BSD-3-Clause), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, GitHub issue/PR templates, `.editorconfig`, `.gitattributes`.
- GitHub Actions CI (Ruff, mypy, pytest + coverage) on Ubuntu and Windows for
  Python 3.9–3.12.

[0.1.0]: https://github.com/digilab-harness/digilab/releases/tag/v0.1.0
