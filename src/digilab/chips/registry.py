"""器件型号注册表。

新增器件：在 `chips/` 下新建 chip_xxxx.py，提供 SPEC 实例，
然后在下面的 _MODULES 列表里追加一个 import 即可。
synthesizer 与 verifier 通过 `get_spec(model)` 查询，永远不需要修改。
"""
from __future__ import annotations

from typing import Dict, List

from . import ChipSpec
from . import chip_7400, chip_7420, chip_74138, chip_74151, chip_74153

_MODULES = [chip_7400, chip_7420, chip_74138, chip_74151, chip_74153]

_REGISTRY: Dict[str, ChipSpec] = {m.SPEC.model: m.SPEC for m in _MODULES}


def get_spec(model: str) -> ChipSpec:
    if model not in _REGISTRY:
        raise KeyError(f"未注册的器件型号：{model}。已注册：{list(_REGISTRY)}")
    return _REGISTRY[model]


def list_models() -> List[str]:
    return sorted(_REGISTRY)
