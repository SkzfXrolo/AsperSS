# Endpoint Detection Rules

## Windows

- baseline Sysmon config (`sysmonconfig-argus.xml` propuesto).
- detección de LOLBins, dumping credenciales, persistencia.

## Linux

- reglas `auditd` (`rules-argus.rules` propuesto).
- monitoreo de cambios en binarios críticos.

## macOS

- endpoint security events para ejecución anómala.

Mapear reglas a MITRE ATT&CK (TTP prioritarias).
