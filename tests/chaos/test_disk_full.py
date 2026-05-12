from __future__ import annotations

import builtins

import pytest


@pytest.mark.chaos
def test_disk_full_simulation(monkeypatch):
    original_open = builtins.open

    def fake_open(*args, **kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(builtins, "open", fake_open)
    with pytest.raises(OSError):
        open("dummy.txt", "w")
    monkeypatch.setattr(builtins, "open", original_open)
