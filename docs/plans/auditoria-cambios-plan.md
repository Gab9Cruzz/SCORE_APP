# Plan: Auditoría de Cambios (tabla `AUDITORIA`)

Generado con `/gstack-autoplan`. Codex no está disponible en esta máquina
(`codex` no está en PATH) — corrió en modo `[subagent-only]`, una sola voz
(Claude), mismo estado que los planes anteriores del repo. El pedido llegó
con una ventana de tiempo corta ("10 minutos para preguntas, después
implementás solo"): se comprimió el ritual de fases CEO/Design/Eng en una
sola pasada de exploración + 2 preguntas de alcance en vez de las 15-30
habituales, y se implementó todo en la misma sesión.

Estado: **IMPLEMENTADO.**

## Pedido

> "El tema de auditoría al 100%, cualquier cambio debe quedar registrado
> durante 1 mes. Creación de evento, modificación, etc."

## Decisiones tomadas con el usuario (D1/D2, ver AskUserQuestion)

- **D1 — Quién puede consultarla:** solo `AdminGeneral`, igual que
  `/accesos` (routes/accesos.py) y por el mismo motivo: expone cambios de
  TODAS las entidades, usuarios incluidos.
- **D2 — Pantalla en el frontend:** sí, `/admin/auditoria`, mismo patrón
  que `/admin/accesos` — una auditoría que nadie puede ver desde la app no
  cumple "que quede registrado" en la práctica.

## Decisión de arquitectura (la que más importa de este plan)

`BaseRepository.create()`/`save_changes()`/`soft_delete()` centralizan el
CRUD de la mayoría de las 18 tablas de negocio, pero **no todas las
escrituras pasan por ahí**: `services/inscripcion_torneo.py`,
`services/motor_formatos.py` (fixtures/sorteos), `services/traspaso.py` y
`services/registro_lote.py` mutan objetos con `session.add()`/`setattr()`
directo. Un hook adentro de `BaseRepository` se habría perdido justo esas
escrituras — nada de "100%".

Se eligió en cambio un **event listener de sesión de SQLAlchemy**
(`backend/app/core/auditoria.py`, `before_flush` + `after_flush_postexec`):
ve TODO lo que el ORM está por escribir en un flush, venga de donde venga.
Es el mismo patrón que la propia documentación de SQLAlchemy usa para
"history tracking". Verificado con
`test_creacion_por_flujo_sin_baserepository_tambien_se_audita`
(`backend/tests/test_auditoria.py`), que ejercita `POST /inscripciones`
(uno de los flujos que NO pasa por `BaseRepository`) y confirma que la fila
de auditoría aparece igual.

Detalles de esa arquitectura (ver el docstring largo del módulo para el
razonamiento completo):

- **Dos eventos, no uno**, por timing: en `before_flush` los objetos
  nuevos todavía no tienen `id` (lo asigna el SERIAL de Postgres recién al
  ejecutar el INSERT) pero es el único momento con el "antes" Y el
  "después" de un UPDATE disponible (`attr.history`). `before_flush` toma
  la foto; `after_flush_postexec` —con los `id` ya asignados— arma las
  filas finales y las inserta con Core (`session.execute(insert(...))`),
  en la MISMA transacción del cambio que audita.
- **Actor vía `contextvars`**, no parámetro extra en cada repositorio:
  `api/deps.py::get_current_user` deja el `usuario_id`/IP/user-agent
  listos en un contextvar en cuanto resuelve el request — aislado por
  Task de asyncio, sin tocar la firma de los ~18 repositorios.
- **`crear`/`modificar`/`eliminar`**: `eliminar` no se adivina por el
  valor de `Estado` (que también cambia en transiciones de negocio
  normales, ej. Torneo → "Finalizado") — `BaseRepository.soft_delete`
  deja un atributo transiente (`obj._auditoria_accion = "eliminar"`) que
  el listener lee y borra. Los "anular" de `evento_partido`/`traspaso`
  (Estado → "Anulado") quedan como `modificar`: son una cancelación de
  negocio, no la baja lógica genérica que `soft_delete` representa.
- **Redacción**: `Usuario.password_hash` nunca aparece en texto plano —
  se reemplaza por `"(redactado)"`, mismo criterio que ya rige para la
  contraseña probada en `/auth/login` (ACCESOS).
- **`fecha_registro`/`fecha_modificacion` se ignoran** en el diff: cambian
  en TODO update por definición (las pisa un trigger de Postgres), así que
  registrarlas es ruido, no dato — `Auditoria.fecha` ya dice cuándo pasó.
- **Retención de 1 mes** (`auditoria_retencion_dias = 30`), purgada al
  arrancar la API — mecanismo idéntico a `accesos_retencion_dias`
  (`app/main.py`), con la misma limitación conocida: un servidor que queda
  semanas sin reiniciarse no purga (ya documentado ahí; si esto pasa a
  correr como servicio permanente, mudar a `pg_cron` o un cron real).

## Qué se construyó

- `database/18_migracion_auditoria_cambios.sql` (tabla `AUDITORIA`,
  aditiva) + `01`-`03_*.sql` actualizados al estado final. Numerada 18 y
  no 15: `15`-`17` ya estaban tomados por `motor-formatos-plantillas-navegacion-plan.md`,
  un plan aparte todavía en curso (sin commitear) al momento de escribir
  esta migración. **Aplicada a `torneos_mvp`** (backup previo en
  `database/backups/torneos_mvp_pre_auditoria_cambios_20260831_001809.dump`).
- Backend: `models/schemas/repositories/routes/auditoria.py`,
  `core/auditoria.py` (el listener), `core/http.py` (helper de IP
  compartido con `/auth/login`, antes duplicado), `config.py`
  (`auditoria_retencion_dias`), purga en `main.py`, hint de
  `BaseRepository.soft_delete`.
- Frontend: `pages/admin/AuditoriaAdmin.tsx` + ruta `/admin/auditoria` +
  link de nav, gateados a `AdminGeneral` igual que Accesos. Filtros por
  tabla (exacto), acción y rango de fechas; columna "Cambios" con el diff
  compacto campo por campo (`antes → después`), texto completo en el
  `title` para lo que no entra en una línea.
- `GET /auditoria` (solo `AdminGeneral`, sin POST/PATCH/DELETE — mismo
  argumento que `/accesos`: una bitácora escribible desde afuera se puede
  falsificar).

## Verificación

- Backend: **202 tests en verde** (191 antes + 11 nuevos en
  `test_auditoria.py`), incluida la migración `18` en
  `test_scripts_sql.py` (corre limpio sobre el esquema actual, dos veces).
- Frontend: **148 tests en verde** (141 antes + 7 nuevos en
  `AuditoriaAdmin.test.tsx`), `tsc -b --noEmit` limpio, `oxlint` limpio,
  `vite build` exitoso.
- `frontend/src/api/schema.d.ts` regenerado contra el backend real
  (`npm run gen:api`).

## Qué quedó explícitamente afuera (ver TODOS.md)

- Filtro por tabla en la UI es texto exacto (sin autocomplete de las 18
  tablas posibles).
- Sin filtro de `registro_id` en la pantalla (sí existe en la API).
- Sin export/descarga (CSV, etc.) de la bitácora.
