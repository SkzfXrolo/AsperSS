import utils.process_tree as pt


class _P:
    def __init__(self, pid, ppid, name):
        self.info = {"pid": pid, "ppid": ppid, "name": name}


def test_get_process_tree(monkeypatch):
    monkeypatch.setattr(pt.psutil, "process_iter", lambda attrs: [_P(1, 0, "a"), _P(2, 1, "b")])
    tree = pt.get_process_tree()
    assert 1 in tree


def test_find_orphans(monkeypatch):
    monkeypatch.setattr(pt.psutil, "process_iter", lambda attrs: [_P(10, 999, "x"), _P(11, 10, "y")])
    out = pt.find_orphans()
    assert any(i["pid"] == 10 for i in out)


def test_find_unusual_ancestors(monkeypatch):
    monkeypatch.setattr(pt.psutil, "process_iter", lambda attrs: [_P(20, 30, "powershell.exe")])
    class PP:
        def name(self): return "WINWORD.EXE"
    monkeypatch.setattr(pt.psutil, "Process", lambda ppid: PP())
    out = pt.find_unusual_ancestors("powershell")
    assert len(out) == 1


def test_find_unusual_ancestors_empty(monkeypatch):
    monkeypatch.setattr(pt.psutil, "process_iter", lambda attrs: [])
    out = pt.find_unusual_ancestors("cmd")
    assert out == []


def test_get_process_tree_empty(monkeypatch):
    monkeypatch.setattr(pt.psutil, "process_iter", lambda attrs: [])
    assert pt.get_process_tree() == {}

