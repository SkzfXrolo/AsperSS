from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.e2e
@pytest.mark.parametrize("path", ["/", "/login", "/panel", "/aspers-sa"])
def test_panel_axe_real(page, base_url, path):
    page.goto(f"{base_url}{path}")
    page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js")
    result = page.evaluate(
        """async () => {
            return await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] } });
        }"""
    )
    out_dir = Path("tests/a11y/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"axe_{path.strip('/').replace('/', '_') or 'root'}.json"
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    critical = [v for v in result.get("violations", []) if v.get("impact") == "critical"]
    assert len(critical) == 0
