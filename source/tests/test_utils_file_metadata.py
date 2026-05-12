from pathlib import Path
import tempfile

import utils.file_metadata as fm


def test_get_file_metadata_hashes(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abc")
        p = tf.name
    monkeypatch.setattr(fm.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": b"Valid"})())
    out = fm.get_file_metadata(p)
    assert "md5" in out and "sha1" in out and "sha256" in out
    Path(p).unlink(missing_ok=True)


def test_get_file_metadata_size(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abcdef")
        p = tf.name
    monkeypatch.setattr(fm.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": b"Valid"})())
    out = fm.get_file_metadata(p)
    assert out["size"] == 6
    Path(p).unlink(missing_ok=True)


def test_get_file_metadata_signature_field(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abc")
        p = tf.name
    monkeypatch.setattr(fm.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": b"UnknownError"})())
    out = fm.get_file_metadata(p)
    assert "signature" in out
    Path(p).unlink(missing_ok=True)


def test_get_file_metadata_timestomp_flag(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abc")
        p = tf.name
    monkeypatch.setattr(fm.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": b"Valid"})())
    out = fm.get_file_metadata(p)
    assert isinstance(out["timestomp_suspected"], bool)
    Path(p).unlink(missing_ok=True)


def test_get_file_metadata_path(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abc")
        p = tf.name
    monkeypatch.setattr(fm.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": b"Valid"})())
    out = fm.get_file_metadata(p)
    assert out["path"] == p
    Path(p).unlink(missing_ok=True)

