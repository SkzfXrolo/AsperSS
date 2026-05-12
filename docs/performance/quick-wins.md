# Pack48-G Quick Wins (Top 20 ROI)

1. Poner `defer` en scripts CDN de `panel.html`.
2. Lazy-load de `chart.js` solo al abrir dashboard visual.
3. Reducir polling cuando `document.hidden === true`.
4. Backoff exponencial tras errores de polling.
5. Split de `panel.js` por secciones principales.
6. Reemplazar `innerHTML` masivo por render incremental.
7. Virtualizar filas de tabla de scans.
8. Optimizar `logo.png` a WebP/AVIF.
9. Consolidar múltiples `COUNT(*)` en query única.
10. Proyección de columnas (evitar `SELECT *`).
11. Cache Redis para stats y pesos AI.
12. Lock distribuido para jobs daemon por worker.
13. Batch de violations HTTP en plugin.
14. Cache `entityId -> Entity` en plugin.
15. Bajar logs INFO de alta frecuencia a FINE.
16. Hash por chunks en scanner (sin `f.read()` completo).
17. Pruning de paths en scans filesystem.
18. Paralelizar sectores del scanner con pool limitado.
19. Baselines automáticos de benchmark por sprint.
20. Alertas SLO burn-rate en vez de solo CPU/RAM.
