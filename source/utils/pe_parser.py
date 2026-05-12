from __future__ import annotations

import struct

from utils.entropy import shannon_entropy
from utils.string_extract import extract_ascii_strings


def parse_pe(path: str) -> dict:
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"MZ":
        return {"is_pe": False}
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off : pe_off + 4] != b"PE\x00\x00":
        return {"is_pe": False}
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    sec_off = pe_off + 24 + opt_size
    sections = []
    for i in range(num_sections):
        o = sec_off + (40 * i)
        name = data[o : o + 8].rstrip(b"\x00").decode("ascii", errors="ignore")
        raw_size = struct.unpack_from("<I", data, o + 16)[0]
        raw_ptr = struct.unpack_from("<I", data, o + 20)[0]
        sec_data = data[raw_ptr : raw_ptr + raw_size] if raw_ptr + raw_size <= len(data) else b""
        sections.append({"name": name, "size": raw_size, "entropy": shannon_entropy(sec_data)})
    imports_guess = [s for s in extract_ascii_strings(data, 5) if s.lower().endswith(".dll")][:50]
    return {"is_pe": True, "sections": sections, "imports_guess": imports_guess}

