from utils.diff import diff_scans


def test_diff_added():
    a = {"issues_found": []}
    b = {"issues_found": [{"tipo": "x", "ruta": "a"}]}
    out = diff_scans(a, b)
    assert len(out["added"]) == 1


def test_diff_removed():
    a = {"issues_found": [{"tipo": "x", "ruta": "a"}]}
    b = {"issues_found": []}
    out = diff_scans(a, b)
    assert len(out["removed"]) == 1


def test_diff_changed():
    a = {"issues_found": [{"tipo": "x", "ruta": "a", "alerta": "SOSPECHOSO"}]}
    b = {"issues_found": [{"tipo": "x", "ruta": "a", "alerta": "CRITICAL"}]}
    out = diff_scans(a, b)
    assert len(out["changed"]) == 1


def test_diff_no_changes():
    a = {"issues_found": [{"tipo": "x", "ruta": "a"}]}
    b = {"issues_found": [{"tipo": "x", "ruta": "a"}]}
    out = diff_scans(a, b)
    assert out["added"] == []
    assert out["removed"] == []
    assert out["changed"] == []


def test_diff_ignores_non_dict():
    a = {"issues_found": ["bad"]}
    b = {"issues_found": []}
    out = diff_scans(a, b)
    assert out["added"] == []
    assert out["removed"] == []

