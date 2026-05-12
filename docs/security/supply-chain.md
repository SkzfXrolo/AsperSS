# Supply Chain Security Review — Pack48 Round 2

Scope: `web_app/requirements.txt`, `minecraft_plugin/argus-mc/pom.xml`, `.github/workflows/*.yml`.

## 1) Python dependencies (`web_app/requirements.txt`)

## Estado

- Mezcla de versiones fijas (`==`) y abiertas (`>=`) sin lockfile reproducible.
- Riesgo de drift entre builds y cambios no controlados en transitive deps.

## Riesgos

- [NEW][MEDIUM] falta de pin estricto/hashes (`--require-hashes`) para cadena de suministro.
- [NEW][MEDIUM] sin SBOM/ciclo automatizado de CVE en CI.

## Recomendaciones

1. generar lock con `pip-compile` o `uv lock`,
2. instalar con hashes (`pip install --require-hashes` en CI),
3. correr `pip-audit`/`osv-scanner` en PR y main,
4. exportar SBOM (CycloneDX).

## 2) Java dependencies (`pom.xml`)

## Estado

- Dependencias principales: `paper-api`, `luckperms`, `packetevents-spigot`.
- Uso de repos externos de terceros.

## Riesgos

- [NEW][MEDIUM] dependencia en repos terceros (riesgo de compromise/takeover).
- [NEW][LOW/MEDIUM] ausencia de validación checksum/firma en pipeline de build.

## Recomendaciones

1. añadir escaneo CVE con `mvn org.owasp:dependency-check-maven:check`,
2. fijar política de mirrors confiables y verificación de artefactos,
3. monitoreo de advisories para PacketEvents/LuckyPerms.

## 3) GitHub Actions workflow security

## Estado

- Se usan actions versionadas por tag (`@v4`, `@v5`, etc.), no por SHA pin.
- No se observaron `@main` en `uses:`.

## Riesgos

- [NEW][MEDIUM] pin por tag sigue siendo mutable en ciertos escenarios de supply-chain.
- [NEW][LOW/MEDIUM] workflows con `contents: write` y releases automáticos elevan impacto ante compromise de pipeline.

## Recomendaciones

1. pin por commit SHA para acciones críticas,
2. permisos mínimos por job (`permissions` granulares),
3. branch protections + required reviews para workflows,
4. activar Dependabot para `github-actions`,
5. opcional Renovate para actualizaciones controladas.

## 4) Provenance y verificación de builds

- [NEW][MEDIUM] no hay attestations/SLSA visibles para artefactos.
- Recomendación: integrar provenance (SLSA/GitHub Artifact Attestations) y checksum firmado por release.
