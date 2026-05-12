# Draft listing para SpigotMC

## Titulo sugerido
Argus Anti-Cheat for Bukkit/Paper - Packet + Behavior Detection

## Resumen
Argus es un anti-cheat orientado a servidores que necesitan deteccion temprana con bajo ruido operativo. Combina chequeos de movimiento/combate y analisis de paquetes para priorizar alertas accionables.

## Caracteristicas clave

- Checks hibridos Bukkit + PacketEvents.
- Modo observador para rollout sin sanciones.
- Integracion con backend Argus AI Oracle para scoring de riesgo.
- Configuracion por umbrales y ventanas de violaciones.
- Diseñado para equipos de moderacion con trazabilidad.

## Compatibilidad

- Java 21 para build/recomendado en runtime.
- Paper/Spigot/Purpur (REVIEW: validar matriz final exacta).
- PacketEvents como dependencia recomendada.

## Instalacion

1. Copiar el `.jar` a `plugins/`.
2. Reiniciar servidor.
3. Editar `plugins/ArgusMC/config.yml` con API key y thresholds.
4. Ejecutar `/argus reload`.

## Soporte

- Documentacion tecnica en `docs/plugin/`.
- REVIEW: agregar Discord/Email oficial del proyecto.
