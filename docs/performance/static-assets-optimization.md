# Static Assets Optimization (Pack48-G)

## Objetivo

Reducir peso y tiempo de carga de CSS/JS/imágenes.

## Checklist

1. Minificar JS/CSS en build.
2. Habilitar gzip + Brotli.
3. Versionar archivos estáticos por hash.
4. Lazy-load de imágenes fuera de viewport.
5. Convertir PNG pesados a WebP/AVIF.
6. `defer` en scripts no críticos.
7. Critical CSS inline para above-the-fold.

## Recomendaciones específicas Argus

- Dividir `panel.js` por módulos.
- Optimizar `logo.png` (actualmente grande).
- Consolidar y limpiar CSS no usado en `argus-ui.css`.

## Métricas objetivo

- JS inicial < 300KB transfer.
- CSS crítico < 50KB.
- LCP < 2.5s en mobile medio.
