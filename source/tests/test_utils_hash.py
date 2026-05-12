import tempfile
from pathlib import Path

from utils.hash_utils import hash_bytes, hash_file


def test_hash_bytes_has_keys():
    out = hash_bytes(b"abc")
    assert set(out.keys()) == {"md5", "sha1", "sha256"}


def test_hash_file_has_keys():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abc")
        p = tf.name
    out = hash_file(p)
    assert "sha256" in out
    Path(p).unlink(missing_ok=True)

