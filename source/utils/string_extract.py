from __future__ import annotations

import re


def extract_ascii_strings(data: bytes, min_len: int = 4):
    pat = rb"[ -~]{%d,}" % min_len
    return [m.decode("ascii", errors="ignore") for m in re.findall(pat, data)]


def extract_unicode_strings(data: bytes, min_len: int = 4):
    pat = rb"(?:[ -~]\x00){%d,}" % min_len
    return [m.decode("utf-16le", errors="ignore") for m in re.findall(pat, data)]

