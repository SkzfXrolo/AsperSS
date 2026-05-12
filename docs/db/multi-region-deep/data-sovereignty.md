# Data sovereignty (Pack 48-H Round 5 · #139)

## Definición

Requisitos legales/contractuales de **dónde** residen y se procesan datos (GDPR, leyes locales, contratos enterprise).

## Implicaciones para Argus

| Tema | Acción técnica |
| --- | --- |
| Residencia UE | Primary o réplica en región EU; backups EU-only |
| Subprocessors | Lista en DPA; Render region documented |
| Transferencias | SCCs / adequacy decisions |
| Derecho supresión | `cleanup-policy-pack48.sql` + DSAR queries (`compliance-report.sql`) |
| Cifrado tránsito | TLS obligatorio |
| Cifrado reposo | Proveedor + opcional column-level (`security-advanced/column-encryption.md`) |

## Multi-region + soberanía

- No replicar PII a región no permitida: usar **subset anonymized** en réplica analytics US si contrato EU lo exige.

## Auditoría

- `staff_audit_log` retention alineada a legal (REVIEW con abogado).

## Referencias

- `docs/db/data-classification.md`
- `docs/db/security-hardening.md`
