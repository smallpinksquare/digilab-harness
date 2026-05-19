"""器件型号注册表。

内置器件：在 ``_MODULES`` 中列出 ``chip_xxxx`` 模块；每个模块暴露 ``SPEC``。

扩展方式（二选一）：

1. **内置**：在 ``_MODULES`` 末尾追加 ``import chip_xxxx`` 模块。
2. **插件**：在任意已安装的发行版里声明 entry-point 组 ``digilab.chips``，
   指向可调用对象（返回 :class:`~digilab.chips.ChipSpec`）或带有 ``SPEC`` 属性的模块。
   若插件型号与内置冲突，**以内置为准**（忽略插件重复项）。
"""

from __future__ import annotations

import importlib.metadata as md

from . import ChipSpec, chip_7400, chip_7420, chip_74138, chip_74151, chip_74153

_MODULES = [chip_7400, chip_7420, chip_74138, chip_74151, chip_74153]


def _iter_chip_plugin_entry_points() -> list[md.EntryPoint]:
    """Return every ``digilab.chips`` entry-point (may be empty)."""
    eps = md.entry_points()
    if hasattr(eps, "select"):
        return list(eps.select(group="digilab.chips"))
    # Python 3.9: dict[str, Sequence[EntryPoint]]
    if isinstance(eps, dict):
        return list(eps.get("digilab.chips", []))
    return []


def _plugin_spec_from_loaded(loaded: object) -> ChipSpec | None:
    """Resolve an entry-point load target to a ``ChipSpec`` if possible."""
    if callable(loaded):
        candidate = loaded()
    elif hasattr(loaded, "SPEC"):
        candidate = loaded.SPEC
    else:
        candidate = loaded
    return candidate if isinstance(candidate, ChipSpec) else None


def _merge_plugin_specs(reg: dict[str, ChipSpec]) -> None:
    """Augment *reg* with plugin specs; builtins always win on name clash."""
    for ep in _iter_chip_plugin_entry_points():
        try:
            loaded = ep.load()
        except Exception:
            continue
        spec = _plugin_spec_from_loaded(loaded)
        if spec is None:
            continue
        if spec.model in reg:
            continue
        reg[spec.model] = spec


_REGISTRY: dict[str, ChipSpec] = {m.SPEC.model: m.SPEC for m in _MODULES}
_merge_plugin_specs(_REGISTRY)


def get_spec(model: str) -> ChipSpec:
    if model not in _REGISTRY:
        raise KeyError(f"未注册的器件型号：{model}。已注册：{list(_REGISTRY)}")
    return _REGISTRY[model]


def list_models() -> list[str]:
    return sorted(_REGISTRY)
