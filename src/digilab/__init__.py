"""digilab: NAND-based digital circuit synthesizer + verifier with breadboard-friendly netlist.

Quick usage::

    from digilab import parse_program_text, synthesize, verify

For the command-line interface, see ``digilab --help`` (after ``pip install -e .``)
or the module ``digilab.cli``.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .common.parser import parse_program_file, parse_program_text
from .synthesizer import synthesize
from .verifier import verify

__all__ = [
    "__version__",
    "parse_program_file",
    "parse_program_text",
    "synthesize",
    "verify",
]
