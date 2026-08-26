# TODOS

## Roles y 3 módulos (Admin General / Torneo Admin / Árbitro)

Plan fase por fase en `docs/plans/roles-3-modulos-plan.md`. Vista al ingresar
para el frontend actual: confirmada sin cambios (Admin y Árbitro comparten
`/dashboard` hasta la Fase 2/3). Empezar por la Fase 1 (backend: roles +
asignación árbitro↔partido) cuando se retome — bloquea a las fases 2-4.

## Frontend — deferido desde el design doc de Dashboard/Control de Mesa/Partido en Vivo

- Qué pasa cuando el árbitro pierde conectividad a mitad de un partido en
  Control de Mesa (offline-first, reintentos, cola local). No definido —
  candidato para `/plan-eng-review` cuando se retome esta área.
- El modelo de datos no distingue titular/suplente. El flujo de Cambio usa
  toda la plantilla vigente como candidatos a entrar/salir (ver limitación
  documentada en `frontend/README.md`). Si se vuelve un problema real en uso,
  evaluar agregar el concepto de "convocados a este partido" en el backend.
