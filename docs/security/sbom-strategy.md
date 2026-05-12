# SBOM Strategy — Argus

## Objetivo

Generar y publicar SBOM por release para mejorar trazabilidad de dependencias y respuesta a CVEs.

## Artefactos objetivo

- Python (`web_app`, scanner libs) -> CycloneDX JSON
- Java plugin (`argus-mc`) -> CycloneDX XML
- JS/panel web -> CycloneDX XML/JSON

## Generación

Script: `scripts/security/generate-sbom.sh`

Herramientas:

- `cyclonedx-py`
- `org.cyclonedx:cyclonedx-maven-plugin`
- `@cyclonedx/bom`

## Publicación

Subir SBOM a:

1. artifacts de CI por commit/release,
2. release assets junto al binario,
3. (opcional) Dependency-Track server para monitoreo continuo.

## Política operativa

- generar SBOM en cada release y en PRs críticas,
- retener historial de SBOM por 12 meses mínimo,
- vincular SBOM con hash del artefacto distribuido.
