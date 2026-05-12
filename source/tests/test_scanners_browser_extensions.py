from pathlib import Path


def test_browser_history_scanner_exists():
    text = Path("source/scanners/browser_history.py").read_text(encoding="utf-8", errors="ignore")
    assert "scan_browser_history" in text

