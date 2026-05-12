# Argus Anti-Cheat para Nekio (Arefy Network)

Argus Anti-Cheat es una solucion enfocada en redes Minecraft que necesitan deteccion consistente sin sobrecargar al staff. El producto combina señales del gameplay (Bukkit) y de red (PacketEvents), priorizando alertas accionables por severidad y contexto.

Para operadores de comunidad, Argus apunta a reducir falsos positivos operativos con un pipeline de violaciones configurable y auditable. La propuesta de valor no es solo "detectar mas", sino permitir decisiones moderadas y graduales con observabilidad.

Para equipos tecnicos, Argus ofrece arquitectura extensible y rollout seguro: observer mode, activacion por fases y tuning fino por umbrales. Esto habilita adopcion en servidores grandes sin frenar la experiencia de jugadores legitimos.

## Comparativa de mercado

| Solucion | Enfoque principal | Señal de paquetes | Rollout gradual | Integracion backend |
| --- | --- | --- | --- | --- |
| Argus | Hibrido (eventos + packets + scoring) | Si (PacketEvents) | Si | Si (AI Oracle) |
| Grim | Prediccion/physics avanzada | Si | Parcial | No nativo |
| Polar | Heuristicas + reglas | Parcial | Parcial | No nativo |
| Vulcan | Reglas comerciales maduras | Si | Parcial | No nativo |
| Verus | Checks clasicos optimizados | Parcial | Limitado | No nativo |

## Cobertura de checks (Bukkit)

1. Speed (horizontal burst)
2. Fly / AirWalk
3. NoFall spoof
4. KillAura angulo imposible
5. Reach extendido
6. AutoClicker CPS anomalo
7. Timer irregular
8. Scaffold placement pattern
9. FastBreak inconsistente
10. FastPlace anormal

## Cobertura de checks (PacketEvents)

1. BadPackets (orden invalido)
2. KeepAlive manipulado
3. Transaction spoof
4. Rotation desync
5. Packet flood burst
6. Inventory packet abuse
7. Position spoof packet-level
8. Ground spoof packet-level
9. UseEntity timing anomaly
10. Interact packet sequence anomaly

## Instalacion (3 pasos)

1. Descargar `argus-mc-<version>.jar` desde releases oficiales.
2. Copiar en `plugins/` y reiniciar el servidor.
3. Editar `plugins/ArgusMC/config.yml`, cargar API key y ejecutar `/argus reload`.

## Configuracion base (`config.yml`)

```yaml
argus:
  apiKey: "TBD_OWNER_ARGUS_KEY"
  observerMode: true
  enforcement:
    enabled: false
    banThreshold: 120
  checks:
    movement:
      speed:
        enabled: true
        threshold: 35
    combat:
      killaura:
        enabled: true
        threshold: 45
```

## FAQ

**1) Argus banea automaticamente al instalarlo?**  
No. Se recomienda iniciar en observer mode.

**2) Necesito PacketEvents para usar Argus?**  
No es obligatorio, pero mejora precision y cobertura.

**3) Como reduzco falsos positivos?**  
Ajustar thresholds por modo de juego y usar rollout gradual.

**4) Es compatible con redes grandes?**  
Si, con monitoreo y tuning por entorno.

**5) Incluye panel web de evidencias?**  
REVIEW: confirmar roadmap exacto del owner para el cliente.

## Pricing / licensing

- Modelo comercial: `TBD`
- Licenciamiento por servidor/red: `TBD`
- Soporte y SLA: `TBD`
