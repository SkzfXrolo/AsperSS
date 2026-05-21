import os
import tempfile

from utils.file_hash_cache import FileHashCache
from utils.hash_utils import sha256_file


def test_cache_returns_same_hash_twice():
    FileHashCache.clear()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"argus-cache-test")
        path = f.name
    try:
        h1 = FileHashCache.sha256(path)
        h2 = FileHashCache.sha256(path)
        assert h1 == h2 == sha256_file(path)
    finally:
        os.unlink(path)
