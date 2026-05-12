# Chaos Experiments Catalog (Pack48-G)

Cada experimento debe definir: **hipótesis**, **blast radius**, **rollback**, **resultado esperado**, **RTO objetivo**.

## Catálogo (30)

1. Kill DB connection mid-query  
2. +5s latency a Redis  
3. Drop 10% packets plugin endpoint  
4. Disk al 95%  
5. CPU 100% en web worker  
6. Crash random worker process  
7. Network partition web<->DB  
8. Cert expiration simulado  
9. Clock skew +30s  
10. Clock skew -30s  
11. DNS failure parcial  
12. SSL handshake failure  
13. Memory leak simulation  
14. Slow disk I/O injection  
15. Forced GC pauses (gen2)  
16. Thread pool saturation  
17. Upstream API rate limited  
18. Cache stampede  
19. Hot key Redis  
20. Schema migration in-flight  
21. Backup job compitiendo con reads  
22. DB failover no planificado  
23. Packet loss 20% regional  
24. Latencia 2s entre regiones  
25. Webhook provider timeout  
26. Queue broker restart abrupto  
27. File descriptor exhaustion  
28. Secrets manager unavailable  
29. NTP drift persistente  
30. CDN edge purge masivo accidental

## Plantilla por experimento

- Hipótesis:
- Blast radius:
- Ejecución:
- Rollback:
- Outcome esperado:
- Recovery time target:
