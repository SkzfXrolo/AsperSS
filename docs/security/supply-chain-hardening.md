# Supply Chain Hardening Plan

## 1) GitHub Actions hardening checklist

- [ ] Pin de actions por SHA (no solo `@v4`).
- [ ] `permissions: read-all` por default.
- [ ] elevar permisos sólo en jobs de release.
- [ ] bloquear cambios a workflows con CODEOWNERS.
- [ ] required reviews para `.github/workflows/**`.

## 2) Tabla de actions actuales y recomendación SHA pin

| Action | Uso actual | Recomendación |
|---|---|---|
| `actions/checkout` | `@v4` | pin a SHA estable de release |
| `actions/setup-python` | `@v5` | pin SHA |
| `actions/setup-java` | `@v4` | pin SHA |
| `actions/upload-artifact` | `@v4` | pin SHA |
| `softprops/action-gh-release` | `@v2` | pin SHA |
| `android-actions/setup-android` | `@v3` | pin SHA |
| `gradle/actions/setup-gradle` | `@v4` | pin SHA |

Nota: los SHAs exactos deben tomarse de releases verificadas al momento de implementación.

## 3) Token scoping

- Evitar `GITHUB_TOKEN` con write fuera de jobs de publicación.
- Usar `permissions` mínimos por job.
- Para firmas/publicación, preferir tokens dedicados de menor alcance.

## 4) Dependabot proposal

`/.github/dependabot.yml` (propuesta; fuera de scope de este worker para crear archivo):

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      gh-actions:
        patterns: ["*"]
  - package-ecosystem: "pip"
    directory: "/web_app"
    schedule:
      interval: "weekly"
  - package-ecosystem: "maven"
    directory: "/minecraft_plugin/argus-mc"
    schedule:
      interval: "weekly"
```

## 5) Sigstore/cosign releases

Objetivo:

- firmar `plugin JAR`, `scanner exe`, `android apk`.
- publicar firma y verificación en release assets.

Flujo sugerido:

1. build artefacto,
2. `cosign sign-blob`,
3. subir `.sig` + checksum,
4. documentar comando de verificación para usuarios.
