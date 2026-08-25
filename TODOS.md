# TODOS

## Frontend — deferido desde el design doc de Dashboard/Control de Mesa/Partido en Vivo

- Qué pasa cuando el árbitro pierde conectividad a mitad de un partido en
  Control de Mesa (offline-first, reintentos, cola local). No definido —
  candidato para `/plan-eng-review` cuando se retome esta área.
- El modelo de datos no distingue titular/suplente. El flujo de Cambio usa
  toda la plantilla vigente como candidatos a entrar/salir (ver limitación
  documentada en `frontend/README.md`). Si se vuelve un problema real en uso,
  evaluar agregar el concepto de "convocados a este partido" en el backend.
