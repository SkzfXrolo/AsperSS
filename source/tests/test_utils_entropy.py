from utils.entropy import shannon_entropy


def test_entropy_empty():
    assert shannon_entropy(b"") == 0.0


def test_entropy_nonzero():
    assert shannon_entropy(b"abcdef") > 0

