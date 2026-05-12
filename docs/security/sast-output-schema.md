# SAST Unified Output Schema

## Formato base

Cada finding normalizado sigue:

```json
{
  "tool": "bandit",
  "severity": "high",
  "cwe": "CWE-78",
  "file": "x.py",
  "line": 42,
  "message": "subprocess shell=True",
  "fix_hint": "Avoid shell=True and validate input."
}
```

## Campos

- `tool`: origen (`bandit|semgrep|gitleaks|pip-audit|safety`)
- `severity`: `low|medium|high|critical`
- `cwe`: identificador CWE (si aplica)
- `file`: ruta afectada
- `line`: línea principal
- `message`: descripción breve
- `fix_hint`: sugerencia de remediación

## Archivos relacionados

- Schema JSON: `scripts/security/sast-schema.json`
- Parser: `scripts/security/sast-parser.py`
- Gate: `scripts/security/sast-gate.py`

## Extender a nuevos tools

1. agregar parser en `sast-parser.py`,
2. mapear severidades a escala común,
3. rellenar `fix_hint` útil,
4. validar contra `sast-schema.json`.
