# Pack48-G Round2: Audit Frontend Performance

## Alcance analizado

- `web_app/templates/panel.html`
- `web_app/static/js/panel.js`
- `web_app/static/css/argus-ui.css` y assets estáticos principales

## Hallazgos clave

### 1) Bundle principal grande y monolítico
- `panel.js` pesa aprox **438 KB** (sin minificación adicional observada en repo).
- Carga funcionalidades de dashboard, scans, admin, IA, modales y animaciones en un único bundle.
- No hay imports dinámicos ni code splitting por sección.

**Impacto estimado:** alto en TTI/parse/execute en móviles y laptops low-end.

### 2) Costo de DOM alto por `innerHTML` masivo
- Se detectan cientos de operaciones de `innerHTML` en `panel.js`.
- Muchas renderizaciones reemplazan bloques completos (listas/tablas/modales) en lugar de patch incremental.
- Riesgo de invalidación de layout y repaint innecesario.

**Impacto estimado:** alto en picos de interacción y en vistas con resultados grandes.

### 3) Polling periódico sin estrategia adaptativa robusta
- Hay múltiples `setInterval(...)` para scans y estados.
- No se observa uso de WebSocket/SSE para updates de estado.
- Falta throttle/debounce estructural en varias interacciones de UI y búsquedas rápidas.

**Impacto estimado:** alto en carga API + CPU cliente durante sesiones largas.

### 4) Bloqueo inicial de render por recursos en `<head>`
- `panel.html` carga varias hojas CSS de forma bloqueante.
- Se cargan scripts CDN (`chart.js`, `canvas-confetti`) en `head` sin `defer/async`.
- Scripts propios van al final (bien), pero los CDN iniciales igual compiten por ruta crítica.

**Impacto estimado:** medio-alto en LCP/FCP.

### 5) Optimización de imágenes limitada
- `web_app/static/img/logo.png` ~836 KB.
- No se detecta variante WebP/AVIF ni `srcset`.

**Impacto estimado:** medio (alto en mobile 3G/4G y primer load).

### 6) Animaciones y efectos visuales
- Hay uso de `requestAnimationFrame` y efectos razonables.
- También se observan zonas con alta manipulación de DOM/estilos y overlays frecuentes.

**Impacto estimado:** medio; depende de hardware cliente.

## Event listeners y riesgo de leaks

- Existe cleanup en algunos modales (`removeEventListener`) pero no uniforme.
- Se agregan listeners en componentes dinámicos que pueden recrearse.
- Riesgo de leaks moderado si rutas de cierre/cleanup no ejecutan siempre.

## Estimación Web Vitals (pre-Lighthouse, basada en arquitectura actual)

- **LCP objetivo:** < 2.5s | **estimado actual:** 2.8s–4.5s en mobile mid-tier.
- **FID/INP objetivo:** < 100ms | **estimado actual:** 90ms–180ms con bursts de render.
- **CLS objetivo:** < 0.1 | **estimado actual:** 0.08–0.18 según carga dinámica de tarjetas/tablas.

> Valores actuales son estimados de arquitectura (no medición de campo real); validar con Lighthouse + CrUX/RUM.

## Recomendaciones priorizadas

1. **Code splitting por sección** (`dashboard`, `resultados`, `admin`, `argusai`).
2. **Migrar updates críticos de polling a SSE/WebSocket** con fallback polling lento.
3. **Reducir `innerHTML` masivo** en listas/tablas; usar render incremental o virtualización.
4. **Mover CDN scripts a `defer`** y cargar `chart.js` lazy cuando se abre la vista que lo usa.
5. **Critical CSS inline + diferir CSS no crítico**.
6. **Imagen logo en WebP/AVIF + `srcset`**.
7. **Debounce/throttle estándar** para búsqueda/filtros.
8. **Estandarizar cleanup de listeners** en todos los modales/overlays.
9. **Service Worker más agresivo** (cache de static versionado).
10. **CDN/HTTP2/HTTP3 + compresión Brotli** para JS/CSS.

## Top mejoras con mejor ROI (frontend)

- `defer` + lazy load scripts pesados.
- split de `panel.js`.
- polling adaptativo con `document.hidden`.
- virtualización de filas de scans.
- optimización de logo y assets críticos.
