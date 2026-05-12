# Frontend Deep Audit (Pack48-G)

## Critical render path

1. HTML parse
2. CSS blocking paint
3. JS blocking interactivity
4. Fonts/images impact LCP

## Blocking resources

- Identificar JS/CSS críticos que frenan render.
- Mover no críticos a `defer/async`.

## Third-party scripts

- Medir impacto de analytics/RUM/Sentry browser SDK.
- Cargar diferido y con sampling donde posible.

## Fonts

- Preferir `font-display: swap` para evitar FOIT.
- Revisar FOUT aceptable visualmente.

## Images

- Jerarquía recomendada: AVIF > WebP > JPEG.
- Lazy loading + tamaños responsivos.
