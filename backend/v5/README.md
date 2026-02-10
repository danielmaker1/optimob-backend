# Backend V5 – Capa Operativa

Objetivo:
Construir una capa operativa mínima encima del motor V4 congelado.

Principios:
- No se modifica la lógica de cálculo de V4.
- V5 gestiona el "HOY": usuarios, rol diario y viajes.
- Separación clara entre planificación (V4) y operación (V5).

Alcance V5:
- Modelo de usuario y rol diario.
- Asignación diaria de viajes (ida/vuelta).
- Validación de viajes (QR / confirmación).
- Endpoints mínimos para frontend.

Fuera de alcance:
- Reoptimización.
- ML.
- GPS en tiempo real.
