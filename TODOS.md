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

## Deferido desde el plan de Equipos y Jugadores (`docs/plans/equipos-jugadores-plan.md`)

- Desactivación de una persona (`JUGADORES.Estado → Inactivo`) que tiene
  perfiles de disciplina o membresías de equipo activas. No definido qué pasa
  con esas membresías (¿se fuerza cierre? ¿se anonimiza?) — es una decisión
  de producto, no solo técnica. Candidato para `/plan-eng-review` cuando se
  retome.
- Límite de tamaño de plantilla para disciplinas de equipo (Fútbol). El plan
  sí limita pareja/individual vía `Modalidad.Tamano_Equipo`, pero no pone
  techo a un roster de fútbol.
- Notificación por correo al jugador cuando es traspasado o pasa a jugador
  libre. El campo `Correo_Electronico` se captura en este módulo pero
  enviarlo es un módulo de notificaciones aparte.
- Importación masiva desde CSV/Excel para el registro por lote. El plan
  asume formulario multi-fila en la UI; si se necesita carga de archivo, es
  una extensión sobre el mismo endpoint de validación.

## Deferido desde el `/review` de equipos-jugadores-plan.md (Fase 3)

- **Cupo de modalidad (EC-6) sin lock.** `RegistroLoteService._validar_lote`
  calcula `cupo_restante` leyendo el conteo de activos una sola vez, sin
  `SELECT ... FOR UPDATE` ni advisory lock — dos `/confirmar` verdaderamente
  simultáneos contra la misma inscripción podrían hacer que un roster de
  modalidad "Dobles" (tope 2) termine con 3 jugadores. Requiere el mismo
  patrón de `pg_advisory_xact_lock` que ya se agregó para la exclusividad
  por torneo (`JugadorEquipoRepository.lock_exclusividad_torneo`), pero
  keyeado por `inscripcion_torneo_id` en vez de `(perfil, torneo)`.
- **Migración `08_migracion_equipos_jugadores.sql`, Parte E, sin rastro de
  auditoría.** Cuando una fila vieja de `JUGADOR_EQUIPO` tiene más de una
  `INSCRIPCIONES_TORNEO` candidata (mismo equipo en torneos solapados), el
  script elige la más antigua y solo deja un `RAISE WARNING` con un conteo
  — no los IDs de las filas ambiguas — y dos sentencias después dropea
  `JUGADOR_ID`/`EQUIPO_ID`, la única fuente que permitiría auditar/corregir
  eso a mano. Ya corrió una vez contra `torneos_mvp` con backup previo, así
  que el riesgo pasado está mitigado; si el script se vuelve a correr contra
  otra base con datos reales, conviene primero volcar los IDs ambiguos a una
  tabla de auditoría temporal (o abortar con `RAISE EXCEPTION` en vez de
  `WARNING` cuando `v_ambiguos > 0`) antes del `DROP COLUMN`.
