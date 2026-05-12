import tempfile
from pathlib import Path

from utils.pe_parser import parse_pe


def test_non_pe():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"hello")
        p = tf.name
    out = parse_pe(p)
    assert out["is_pe"] is False
    Path(p).unlink(missing_ok=True)

