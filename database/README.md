# `/database` — esquema SQL

Este proyecto **no usa Alembic**. El esquema vive en SQL puro acá y la API
solo lo mapea (ver `backend/README.md`). Eso hace que la numeración de los
archivos importe: no todos los `.sql` son lo mismo, y confundirlos cuesta
caro.

## Las tres familias de archivos

### 1. `01`–`06` — el esquema actual, siempre al día

```
01_schema.sql       tablas
02_constraints.sql  FK, CHECK, UNIQUE
03_indexes.sql      índices
04_views.sql        vistas
05_seed.sql         datos mínimos para que la app arranque
06_triggers.sql     funciones + triggers (las reglas de negocio "duras")
```

**Describen el estado FINAL del esquema, no su historia.** Cuando un plan
cambia el modelo, estos archivos se editan hasta dejarlos como si el
esquema siempre hubiera sido así.

Son la fuente de verdad de dos cosas: una instalación nueva y
`backend/tests/conftest.py`, que reconstruye `torneos_mvp_test` desde acá
en cada corrida. **Si tocás el esquema, tocás estos archivos.**

### 2. `07`–`09`, `12`–`14` — migraciones históricas

Cada una aplica un plan concreto sobre una base **ya provisionada**
(`torneos_mvp`), donde no se puede simplemente recrear todo:

| Archivo | Plan |
|---|---|
| `07_migracion_roles_arbitro.sql` | `roles-3-modulos-plan.md` |
| `08_migracion_equipos_jugadores.sql` | `equipos-jugadores-plan.md` |
| `09_migracion_torneo_ediciones.sql` | `torneos-admin-plan.md` |
| `12_migracion_catalogo_disciplinas.sql` | `ediciones-catalogo-disciplinas-plan.md` |
| `13_migracion_equipos_disciplina.sql` | `equipos-disciplina-navegacion-plan.md` |
| `14_migracion_auditoria_accesos.sql` | Bitácora de inicios de sesión (tabla `ACCESOS`) |

**Una migración vieja no tiene por qué correr sobre el esquema de hoy, y
eso no es un bug.** `08` referencia `DISCIPLINA.Tipo`, una columna que `12`
eliminó: aplicarla sobre una base actual falla, y está bien — su trabajo ya
está incorporado en `01`–`06`. Son un registro de cómo se llegó acá, no
scripts re-aplicables para siempre.

La única que sí debe seguir corriendo limpio sobre el esquema actual es la
**última** (hoy `14`), porque sobre el estado final es un no-op — y eso lo
verifica un test (ver abajo).

### 3. `10`, `11` — datos, no esquema

| Archivo | Qué es |
|---|---|
| `10_demo_torneos_admin.sql` | Escenario de demostración (Liga Relámpago con 2 ediciones superpuestas, Copa Raíces de Tenis, Micky con dos perfiles aislados). Para tener algo que mostrar en desarrollo. |
| `11_catalogo_disciplinas.sql` | Catálogo maestro: 28 disciplinas / 66 modalidades. |

**Estos SÍ tienen que correr siempre sobre una base al día**, y son
re-ejecutables (cada `INSERT` chequea antes si ya existe).

Son los más fáciles de romper sin darse cuenta: no los cubre ningún test
de la app. `equipos-disciplina-navegacion-plan.md` agregó dos columnas
`NOT NULL` a `EQUIPOS` y dejó `10_demo_torneos_admin.sql` roto mientras
los 140 tests seguían en verde. Por eso ahora existe
`backend/tests/test_scripts_sql.py`: crea una base desde `01`–`06`, corre
`10`, `11` y la última migración encima **dos veces** y verifica que los datos que dejan
sean coherentes. Si volvés a cambiar el esquema, ese test es el que avisa.

## Correr una migración contra `torneos_mvp`

1. **Backup primero**, siempre — van a `backups/`:
   ```powershell
   $ts = Get-Date -Format "yyyyMMdd_HHmmss"
   & "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -h 127.0.0.1 -U postgres `
       -F c -f "database\backups\torneos_mvp_pre_<cambio>_$ts.dump" torneos_mvp
   ```

2. **Probala contra una base descartable antes**, no contra la real. Para
   la `13` está `backend/scripts/verificar_migracion_13.py`, que arma una
   base con el esquema viejo, ejercita los casos borde (equipos ambiguos y
   huérfanos), verifica el frenazo, la resolución manual y la
   idempotencia. Sirve de molde para la próxima.

3. **Corré el archivo entero en UNA transacción.** No es un detalle
   menor: varias de estas migraciones se detienen a propósito con un
   `RAISE EXCEPTION` cuando encuentran datos que necesitan una decisión
   humana. En una sola transacción ese frenazo revierte todo y la base
   queda intacta; con `psql -f` (autocommit por sentencia) quedan aplicadas
   las partes anteriores al frenazo.

   ```powershell
   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database\13_....sql
   ```

   (El `-1` es lo que la envuelve en una transacción.)

4. **Actualizá `01`–`06`** al estado final en el mismo cambio, o la
   próxima instalación nueva y los tests van a describir otro esquema que
   producción.

## Restaurar un backup

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -h 127.0.0.1 -U postgres `
    -d torneos_mvp --clean --if-exists "database\backups\<archivo>.dump"
```

## Diagrama

`esquema_relacional_torneos.html` — diagrama entidad-relación navegable.
Abrilo en el navegador.
