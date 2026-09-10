"""Check that main.walk_bounded respeta depth, time budget y poda de dirs."""
import os
import time

import main


def _mktree(base):
    # base/a/b/c/d/e/f/g/h/i  (9 niveles) + base/windows/junk
    p = base
    for name in list("abcdefghi"):
        p = os.path.join(p, name)
        os.makedirs(p, exist_ok=True)
        open(os.path.join(p, f"file_{name}.txt"), "w").close()
    skip = os.path.join(base, "windows", "winsxs")
    os.makedirs(skip, exist_ok=True)
    open(os.path.join(skip, "poison.txt"), "w").close()
    nm = os.path.join(base, "a", "node_modules", "pkg")
    os.makedirs(nm, exist_ok=True)
    open(os.path.join(nm, "index.js"), "w").close()


def test_depth_and_skip(tmp_path):
    base = str(tmp_path)
    _mktree(base)
    seen = [r for r, _d, _f in main.walk_bounded([base], max_depth=4, time_budget=30)]
    seen_l = [s.lower() for s in seen]

    # nada por debajo de max_depth=4
    assert not any(os.path.join("d", "e") in s for s in seen)
    # dirs ruidosos podados
    assert not any("winsxs" in s for s in seen_l)
    assert not any("node_modules" in s for s in seen_l)
    # sí llega a los primeros niveles
    assert any(s.rstrip("\\/").endswith(os.sep + "a") for s in seen)


def test_time_budget_stops(tmp_path):
    base = str(tmp_path)
    _mktree(base)
    t0 = time.time()
    list(main.walk_bounded([base], max_depth=99, time_budget=0.001))
    assert time.time() - t0 < 2.0  # sale por deadline, no recorre todo


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        class _P:
            def __init__(s, x): s._x = x
            def __str__(s): return s._x
        test_depth_and_skip(_P(d))
    with tempfile.TemporaryDirectory() as d:
        test_time_budget_stops(_P(d))
    print("OK")
