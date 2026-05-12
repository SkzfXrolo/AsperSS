# SOC 2 Controls Matrix (64 controls)

Status legend: `implemented | partial | gap | n/a`.

| Control | Domain | Status | Nota |
|---|---|---|---|
| C01 | Security | partial | MFA admins pendiente |
| C02 | Security | implemented | RBAC base |
| C03 | Security | partial | hardening sessions |
| C04 | Security | gap | anti-replay global |
| C05 | Security | partial | rate-limit incompleto |
| C06 | Security | gap | pinning clientes |
| C07 | Security | partial | secret rotation |
| C08 | Security | partial | vuln mgmt |
| C09 | Security | partial | SAST gating |
| C10 | Security | partial | DAST programado |
| C11 | Security | implemented | audit docs |
| C12 | Security | gap | WAF full rollout |
| C13 | Availability | partial | SLO formal |
| C14 | Availability | partial | failover testing |
| C15 | Availability | gap | DR drill regular |
| C16 | Availability | partial | backup strategy |
| C17 | Availability | partial | incident comms |
| C18 | Availability | implemented | health checks |
| C19 | Availability | partial | capacity planning |
| C20 | Availability | gap | chaos testing prod-like |
| C21 | Processing Integrity | partial | input validation gaps |
| C22 | Processing Integrity | partial | schema validation |
| C23 | Processing Integrity | partial | idempotencia jobs |
| C24 | Processing Integrity | gap | replay-safe pipeline |
| C25 | Processing Integrity | partial | traceability |
| C26 | Processing Integrity | implemented | error handling base |
| C27 | Processing Integrity | partial | SLA fix bugs |
| C28 | Processing Integrity | gap | signed artifacts |
| C29 | Processing Integrity | partial | SBOM rollout |
| C30 | Processing Integrity | partial | pipeline controls |
| C31 | Confidentiality | partial | data classification |
| C32 | Confidentiality | gap | encryption-at-rest formal |
| C33 | Confidentiality | partial | secrets hygiene |
| C34 | Confidentiality | gap | key mgmt central |
| C35 | Confidentiality | partial | least privilege |
| C36 | Confidentiality | partial | log redaction |
| C37 | Confidentiality | gap | periodic access review |
| C38 | Confidentiality | partial | vendor controls |
| C39 | Confidentiality | partial | retention policy |
| C40 | Confidentiality | implemented | secure transport baseline |
| C41 | Privacy | gap | DSAR endpoints |
| C42 | Privacy | partial | legal basis doc |
| C43 | Privacy | gap | SoP deletion requests |
| C44 | Privacy | partial | minimization policy |
| C45 | Privacy | partial | privacy notices |
| C46 | Privacy | gap | RoPA formal |
| C47 | Privacy | gap | DPIA routine |
| C48 | Privacy | partial | consent logic review |
| C49 | Privacy | partial | retention enforcement |
| C50 | Privacy | partial | incident privacy workflow |
| C51 | Cross | implemented | security policy |
| C52 | Cross | partial | secure SDLC |
| C53 | Cross | partial | dev training |
| C54 | Cross | partial | tabletop exercises |
| C55 | Cross | gap | KPI dashboard live |
| C56 | Cross | partial | vendor reassessment cadence |
| C57 | Cross | partial | change management |
| C58 | Cross | partial | evidence repository |
| C59 | Cross | gap | formal risk register |
| C60 | Cross | partial | third-party monitoring |
| C61 | Cross | partial | policy exceptions process |
| C62 | Cross | gap | control automation depth |
| C63 | Cross | partial | board-level reporting |
| C64 | Cross | partial | continuous compliance |

## Priorización de gaps críticos

1. C04 anti-replay,
2. C06 pinning,
3. C41-C43 DSAR/Privacy process,
4. C32/C34 encryption & key mgmt,
5. C55 KPI dashboard operativo.
