# `/docs/queries` — métricas ad hoc, versionadas

Este directorio no es un dashboard: es el registro en SQL de consultas que
se corrieron a mano para responder una pregunta puntual de producto (¿hay
volumen suficiente para justificar tal feature?, ¿esta decisión diferida ya
debería reabrirse?). El repo no tiene pipeline de métricas — este es el
sustituto liviano, versionado igual que el resto del código.

## Cómo correr una consulta

Contra `torneos_mvp` (dev/producción), nunca contra las bases de test (esas
se reconstruyen solas y no tienen datos orgánicos):

```powershell
psql -h 127.0.0.1 -U postgres -d torneos_mvp -f docs\queries\<archivo>.sql
```

Registrá el resultado en `TODOS.md`, junto al ítem que la consulta
responde — **un resultado en cero es un hallazgo que vale registrar**, no
un motivo para no anotarlo. "Sin volumen suficiente todavía" es una
respuesta válida y es la que suele salir la primera vez.

## Separar filas orgánicas de las sintéticas

`backend/scripts/mock_estres_catalogo.py` dejó datos de prueba de estrés en
`torneos_mvp` a propósito (cédulas `MOCK-%`, torneos del grupo "Prueba de
Estrés"). Cualquier consulta que cuente filas para argumentar una decisión
tiene que excluirlos explícitamente, o el conteo mide carga sintética, no
uso real.

## Trampa de casing en `AUDITORIA.Tabla`

`backend/app/core/auditoria.py` guarda `obj.__tablename__` en la columna
`Tabla` — eso es **minúscula** (`usuarios`, `partidos`...), no el nombre de
la clase Python ni el de la tabla en mayúsculas. Filtrar `Tabla='USUARIOS'`
da cero por casing, no por falta de datos.

## Consultas existentes

- `metricas-desempate-tiempo-extra-penales.sql` — volumen de torneos de
  Eliminación con llaves desempatadas, para decidir si vale la pena tratar
  el tiempo extra como reloj real (Fase 3 del plan de desempate).
