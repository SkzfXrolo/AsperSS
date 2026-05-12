from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "argus_ai_oracle",
        "argus_ai_features",
        "argus_ai_trainer",
        "argus_ai_labeler",
        "argus_ai_assistant",
    ],
)
def test_module_import_smoke(module_name):
    mod = importlib.import_module(module_name)
    assert mod is not None


@pytest.mark.parametrize(
    "module_name",
    [
        "argus_ai_oracle",
        "argus_ai_features",
        "argus_ai_trainer",
        "argus_ai_labeler",
        "argus_ai_assistant",
    ],
)
def test_main_guard_smoke(module_name):
    # Estos módulos no deberían ejecutar efectos destructivos al importar.
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "__name__")
