# PCI DSS Applicability Review

## ¿Aplica PCI DSS a Argus?

Si Argus **no** procesa, transmite ni almacena PAN de tarjetas directamente, el scope PCI puede ser mínimo o no aplicable.

## Escenarios

- checkout alojado por Stripe/PayPal (hosted): scope reducido (típicamente SAQ A).
- procesamiento directo en backend propio: scope amplio (SAQ D).

## Recomendación

Usar checkout completamente hospedado y tokenizado por PSP para mantener Argus fuera de scope PCI pesado.

## Si aplica

- definir CDE (Cardholder Data Environment),
- segmentar red y accesos,
- logging, scanning ASV, pentest y hardening anual.
