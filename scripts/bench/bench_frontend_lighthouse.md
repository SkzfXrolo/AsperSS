# Bench Frontend con Lighthouse (Pack48-G)

## Objetivo

Medir performance real de frontend en producción pública:
- `https://asperss.onrender.com`

## Comando base

```bash
npx lighthouse https://asperss.onrender.com --view --output=html --output-path=./lh-report.html
```

## Comandos recomendados adicionales

Desktop:

```bash
npx lighthouse https://asperss.onrender.com --preset=desktop --output=json --output=html --output-path=./lh-desktop
```

Mobile simulado:

```bash
npx lighthouse https://asperss.onrender.com --form-factor=mobile --throttling-method=simulate --output=json --output=html --output-path=./lh-mobile
```

## Targets esperados

| Métrica | Target | Interpretación |
|---|---:|---|
| Performance score | >= 80 | Salud general de rendimiento. |
| LCP | < 2.5s | Tiempo de render del contenido principal. |
| INP/FID | < 100ms | Responsividad de interacción. |
| CLS | < 0.1 | Estabilidad visual. |
| TBT | < 200ms | Bloqueo total del main thread. |
| JS transfer | < 300KB inicial | Costo de descarga/parsing de scripts críticos. |
| Requests | < 60 iniciales | Menos roundtrips en primer render. |

## Cómo leer el reporte

1. Si LCP alto y TBT bajo: foco en imágenes/CSS crítico/network.
2. Si TBT alto: foco en JS monolítico, listeners y render masivo.
3. Si CLS alto: revisar placeholders, tamaño reservado de imágenes/cards.
4. Si performance móvil cae fuerte vs desktop: priorizar split de bundle y assets.

## Frecuencia recomendada

- Ejecutar al menos 1 vez por sprint.
- Ejecutar siempre antes de release mayor de UI.
- Guardar JSON para comparar regresiones con baseline.
