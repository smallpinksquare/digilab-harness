"""Tests for ``digilab.chips.registry`` (built-ins + plugin resolution helpers)."""

from __future__ import annotations

from types import SimpleNamespace

from digilab.chips.registry import _plugin_spec_from_loaded, get_spec, list_models


def test_list_models_includes_all_builtins() -> None:
    names = set(list_models())
    assert names == {"7400", "7420", "74138", "74151", "74153"}


def test_plugin_spec_from_loaded_callable() -> None:
    s = get_spec("7400")
    assert _plugin_spec_from_loaded(lambda: s) is s


def test_plugin_spec_from_loaded_module_like() -> None:
    s = get_spec("7400")
    assert _plugin_spec_from_loaded(SimpleNamespace(SPEC=s)) is s


def test_plugin_spec_from_loaded_invalid() -> None:
    assert _plugin_spec_from_loaded("not-a-spec") is None
