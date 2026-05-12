# Proposal: `.github/workflows/security-scan.yml`

Nota: este worker mantiene scope en `docs/security/**`, `tests/security/**`, `scripts/security/**`, por eso se deja propuesta textual.

```yaml
name: Security Scan

on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<PINNED_SHA>
      - uses: actions/setup-python@<PINNED_SHA>
        with:
          python-version: "3.11"
      - name: Install tools
        run: |
          python -m pip install --upgrade pip
          pip install bandit semgrep gitleaks pip-audit safety
      - name: Run SAST
        run: |
          bash scripts/security/run-sast.sh
      - name: Upload reports
        uses: actions/upload-artifact@<PINNED_SHA>
        with:
          name: security-sast-reports
          path: security-artifacts/sast
      - name: Fail on critical
        run: |
          # placeholder: parse JSON reports and fail if critical findings > 0
          echo "Implement parser for critical severity gating"
```
