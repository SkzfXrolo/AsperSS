# 40 mejoras visuales — Argus Scanner UI

| # | Mejora | Estado |
|---|--------|--------|
| 1 | Barra de título custom (arrastrar ventana sin borde Windows) | ✅ v3 |
| 2 | Botones minimizar / cerrar con hover cobre | ✅ v3 |
| 3 | Badge de versión en header (`v1.6.50`) | ✅ v3 |
| 4 | Fade-in al abrir ventana (opacidad 0→1) | ✅ v3 |
| 5 | Vignette en esquinas (profundidad) | ✅ v3 |
| 6 | Tarjeta de progreso con borde doble / glow | ✅ v3 |
| 7 | Anillo de progreso cambia color por % (cobre→ámbar→verde) | ✅ v3 |
| 8 | Etiqueta interior del anillo (`SCAN` / `%`) | ✅ v3 |
| 9 | Modo escaneo: anillo más rápido + partícula orbital | ✅ (ya existía, reforzado) |
| 10 | Barra inferior con shimmer continuo | ✅ (ya existía) |
| 11 | Indicador de pasos (dots de fase) | ✅ v3 |
| 12 | Fade al cambiar texto de fase/detalle | ✅ v3 |
| 13 | Chips CRIT/SOSP/BAJO/OK con borde de color | ✅ v3 |
| 14 | Animación flash al subir contador | ✅ v3 |
| 15 | Barra de riesgo (risk meter) bajo contadores | ✅ v3 |
| 16 | Mini-barras CPU/RAM en recursos | ✅ v3 |
| 17 | Timer con separador parpadeante | ✅ v3 |
| 18 | Botón cancelar con borde hover | ✅ v3 |
| 19 | Panel completado con resumen CRIT·SOSP·Total | ✅ (previo) |
| 20 | Confetti cobre al completar con éxito | ✅ v3 |
| 21 | Panel error en rojo pulsante | ✅ v3 |
| 22 | Badge estado: icono según modo (● ◉ ✓) | ✅ v3 |
| 23 | Separador header con shimmer | ✅ (ya existía) |
| 24 | Logo con halo al hover | ✅ v3 |
| 25 | Watermark footer `Argus Projects` | ✅ v3 |
| 26 | Transición scan → completado (oculta progreso) | ✅ (previo) |
| 27 | Recorte de fase larga con … | ✅ (previo) |
| 28 | Esquinas redondeadas Win11 + borde DWM cobre | ✅ (ya existía) |
| 29 | Tipografía jerárquica (título / fase / detalle) | ✅ v3 |
| 30 | Cursor hand2 en controles interactivos | ✅ v3 |
| 31 | Top hallazgo en panel completado | ✅ v3 |
| 32 | Risk score numérico junto al meter | ✅ v3 |
| 33 | Color de barra de riesgo por severidad | ✅ v3 |
| 34 | Pulso en badge al escanear | ✅ (ya existía) |
| 35 | Detalle en Consolas (look terminal) | ✅ (ya existía) |
| 36 | Ventana fija 705×279 (compacta SS) | ✅ (mantener) |
| 37 | Modo alto contraste (toggle futuro) | 🔜 |
| 38 | Sonido + flash al terminar (opcional) | 🔜 |
| 39 | Tooltip en chips (hover texto ayuda) | 🔜 |
| 40 | Tema claro alternativo | 🔜 |

Implementación principal: `source/ui_style.py` (UI v3) + hooks en `source/main.py`.
