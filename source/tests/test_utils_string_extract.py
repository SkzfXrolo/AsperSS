from utils.string_extract import extract_ascii_strings, extract_unicode_strings


def test_extract_ascii():
    out = extract_ascii_strings(b"xxhello_worldyy", min_len=5)
    assert any("hello" in s for s in out)


def test_extract_unicode():
    data = "test".encode("utf-16le")
    out = extract_unicode_strings(data, min_len=4)
    assert "test" in out

