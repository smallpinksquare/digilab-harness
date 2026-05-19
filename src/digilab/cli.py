"""digilab unified command-line interface.

Sub-commands:

* ``digilab synth   --expr <expr.md> --out <dir>``  thin wrapper around
  :func:`digilab.synthesizer.main`.
* ``digilab verify  --netlist <netlist.json> --truth <truth.csv> --out <dir>``
  thin wrapper around :func:`digilab.verifier.main`.
* ``digilab selftest``  run the in-file ``_self_check()`` of every registered
  chip module. Modules without ``_self_check`` are silently skipped.

The wrappers keep argparse behaviour of the underlying ``main`` functions
intact, so existing scripts that called ``python -m digilab.synthesizer ...``
continue to work too.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence

from . import __version__

# chip_<model>.py naming matches every built-in (7400, 7420, 74138, …).
# Plugin-only models must ship a module digilab_chips_<foo> with its own
# selftest or register a chip_* module — for now selftest only imports chip_<model>.


def _run_synth(argv: list[str]) -> int:
    from .synthesizer import main as synth_main

    return synth_main(argv)


def _run_verify(argv: list[str]) -> int:
    from .verifier import main as verify_main

    return verify_main(argv)


def _run_selftest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="digilab selftest",
        description="run the per-chip _self_check() of every registered chip",
    )
    parser.parse_args(argv)

    passed: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    from .chips.registry import list_models

    for model in sorted(list_models()):
        mod_name = f"chip_{model}"
        full = f"digilab.chips.{mod_name}"
        try:
            mod = importlib.import_module(full)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{mod_name}: import error: {exc!r}")
            continue
        fn = getattr(mod, "_self_check", None)
        if fn is None:
            skipped.append(mod_name)
            continue
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{mod_name}: {exc}")
        else:
            passed.append(mod_name)

    print(f"passed:  {len(passed)}  {passed}")
    print(f"skipped: {len(skipped)} (no _self_check)  {skipped}")
    print(f"failed:  {len(failed)}")
    for line in failed:
        print(f"  ! {line}")
    return 0 if not failed else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="digilab",
        description="digilab: NAND-based digital circuit synthesizer + verifier",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"digilab {__version__}",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="{synth,verify,selftest}", required=True)
    sub.add_parser(
        "synth",
        add_help=False,
        help="expression.md -> circuit.txt + netlist.json",
    )
    sub.add_parser(
        "verify",
        add_help=False,
        help="netlist + truth table -> verify report",
    )
    sub.add_parser(
        "selftest",
        help="run per-chip self-checks",
    )

    argv_list = list(argv) if argv is not None else None
    args, rest = parser.parse_known_args(argv_list)

    if args.cmd == "synth":
        return _run_synth(rest)
    if args.cmd == "verify":
        return _run_verify(rest)
    if args.cmd == "selftest":
        return _run_selftest(rest)
    parser.error(f"unknown sub-command: {args.cmd}")
    return 2  # unreachable but keeps mypy happy


if __name__ == "__main__":
    sys.exit(main())
