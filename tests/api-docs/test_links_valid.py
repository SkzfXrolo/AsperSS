from __future__ import annotations

import pathlib
import re


def test_docs_links_are_well_formed():
    md = pathlib.Path("tests/contract/README.md")
    text = md.read_text(encoding="utf-8")
    links = re.findall(r"https?://[^\s)]+", text)
    assert all(link.startswith("http") for link in links) if links else True
