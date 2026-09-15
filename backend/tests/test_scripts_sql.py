"""Los scripts SQL de /database que tienen que seguir funcionando contra el
esquema ACTUAL, corridos de verdad contra una base descartable.

Por qué existe este archivo: el resto de la suite construye su base desde
01-06 y nunca toca los scripts numerados 10+. Eso deja un hueco real —
`equipos-disciplina-navegacion-plan.md` agregó dos columnas NOT NULL a
EQUIPOS y rompió `10_demo_torneos_admin.sql` (que insertaba equipos solo
con Nombre) sin que ninguno de los 140 tests se enterara: la app y sus
tests quedaron sanos, y el script con el que se levanta un entorno de
desarrollo, roto. Se descubrió a mano.

Qué se prueba y qué NO:

- SÍ: los scripts que deben poder correr sobre una base al día — el seed
  de demo (10), el catálogo maestro (11) y las migraciones de auditoría
  (14 y 18 — este archivo no cubre 15/16/17, de un plan aparte todavía en
  curso), que sobre el esquema final son un no-op. Se corren DOS veces:
  todos se documentan como re-ejecutables, y esa promesa también se
  verifica.
- NO: 07/08/09/12/13. Son migraciones HISTÓRICAS, escritas para el esquema
  que existía cuando se aplicaron; 08 referencia `DISCIPLINA.Tipo`, que
  12 eliminó. Que fallen sobre el esquema actual es correcto, no un bug —
  su trabajo ya está incorporado en 01-06.

Es el test más lento de la suite (construye una base entera), así que crea
UNA sola base para todo el módulo y la reusa.
"""
import pathlib

import asyncpg
import pytest
import pytest_asyncio

from tests.conftest import DATABASE_DIR, SQL_FILES, _connect, _url

SCRIPTS_VIGENTES = [
    "10_demo_torneos_admin.sql",
    "11_catalogo_disciplinas.sql",
    "14_migracion_auditoria_accesos.sql",
    "18_migracion_auditoria_cambios.sql",
    "19_migracion_plantilla_base_equipo.sql",
    "20_migracion_control_mesa_tiempos.sql",
    "21_migracion_desempate_manual.sql",
    "22_migracion_rate_limiting_login.sql",
    "23_migracion_archivar_torneo_grupo.sql",
    "24_migracion_limites_y_walkover.sql",
    "25_migracion_convocados.sql",
    "27_migracion_minimo_titulares.sql",
    "28_migracion_reglas_cambio.sql",
    "29_migracion_maximo_titulares.sql",
    "30_migracion_fin_forzado.sql",
    "31_migracion_portal_publico.sql",
]

# F10/E-L6 (portal-publico-feed-partidos-plan.md): el test de cobertura de
# directorio de abajo exige que TODO archivo de /database quede en una de
# las dos listas. Estos son migraciones HISTÓRICAS (escritas para un
# esquema que ya no existe — ver el docstring del módulo) o migraciones de
# un plan aparte todavía en curso, no cubierto por este archivo: si algún
# día se integran a SCRIPTS_VIGENTES, se sacan de acá.
SCRIPTS_HISTORICOS = [
    "07_migracion_roles_arbitro.sql",
    "08_migracion_equipos_jugadores.sql",
    "09_migracion_torneo_ediciones.sql",
    "12_migracion_catalogo_disciplinas.sql",
    "13_migracion_equipos_disciplina.sql",
    "15_migracion_popularidad_disciplinas.sql",
    "16_migracion_foto_jugadores.sql",
    "17_migracion_motor_formatos.sql",
    "26_migracion_rbac_licencias_torneos.sql",
]

# Seeds que se corren a mano cuando hacen falta (ej. `seed_portal_demo.sql`,
# portal-publico-feed-partidos-plan.md F1) — no numerados, no forman parte
# del camino de migración automático ni prometen correr limpio contra
# CUALQUIER estado de la base (ej. seed_portal_demo.sql asume que
# 11_catalogo_disciplinas.sql ya corrió), así que quedan fuera de
# SCRIPTS_VIGENTES a propósito.
SEEDS_MANUALES = [
    "seed_portal_demo.sql",
]

DB_SCRIPTS = "torneos_mvp_scripts_test"


@pytest_asyncio.fixture(scope="module")
async def base_al_dia():
    """Base construida solo con 01-06 — el mismo estado "final" del que
    sale la base de tests, y el que tendría una instalación nueva."""
    maint = await _connect("postgres")
    try:
        await maint.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            DB_SCRIPTS,
        )
        await maint.execute(f'DROP DATABASE IF EXISTS "{DB_SCRIPTS}"')
        await maint.execute(f'CREATE DATABASE "{DB_SCRIPTS}"')
    finally:
        await maint.close()

    con = await asyncpg.connect(
        host=_url.host or "localhost",
        port=_url.port or 5432,
        user=_url.username,
        password=_url.password,
        database=DB_SCRIPTS,
    )
    for filename in SQL_FILES:
        await con.execute((DATABASE_DIR / filename).read_text(encoding="utf-8"))

    yield con

    await con.close()
    maint = await _connect("postgres")
    try:
        await maint.execute(f'DROP DATABASE IF EXISTS "{DB_SCRIPTS}"')
    finally:
        await maint.close()


@pytest.mark.parametrize("script", SCRIPTS_VIGENTES)
async def test_script_corre_sobre_el_esquema_actual(base_al_dia, script: str):
    """El script no puede reventar contra una base construida con 01-06.

    Corre en orden gracias a que pytest ejecuta los parámetros en el orden
    declarado y todos comparten la misma base del fixture de módulo: 10
    carga la demo, 11 el catálogo encima, y la última migración verifica
    que sobre el esquema final no tenga nada que migrar.
    """
    sql = (DATABASE_DIR / script).read_text(encoding="utf-8")
    try:
        await base_al_dia.execute(sql)
    except Exception as e:  # noqa: BLE001 — se re-lanza con contexto útil
        pytest.fail(f"{script} falló contra el esquema actual (01-06):\n  {type(e).__name__}: {e}")


@pytest.mark.parametrize("script", SCRIPTS_VIGENTES)
async def test_script_es_reejecutable(base_al_dia, script: str):
    """Los tres se documentan como "se puede correr más de una vez sin
    romper nada". Se corren por segunda vez sobre la base que el test
    anterior ya dejó cargada: si alguno duplicara filas o chocara contra
    un UNIQUE, acá revienta."""
    sql = (DATABASE_DIR / script).read_text(encoding="utf-8")
    try:
        await base_al_dia.execute(sql)
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"{script} no es re-ejecutable:\n  {type(e).__name__}: {e}")


async def test_la_demo_deja_datos_coherentes_con_el_filtro_por_disciplina(base_al_dia):
    """Regresión puntual del bug que motivó este archivo: los equipos que
    carga la demo tienen que tener disciplina, y tiene que ser la MISMA que
    la del torneo al que la demo los inscribe — si no, son datos que la
    propia API ya no dejaría crear (EC-33)."""
    sin_disciplina = await base_al_dia.fetchval(
        "SELECT COUNT(*) FROM EQUIPOS WHERE Disciplina_ID IS NULL OR Modalidad_ID IS NULL"
    )
    assert sin_disciplina == 0, f"{sin_disciplina} equipo(s) de la demo sin disciplina/modalidad"

    cruzadas = await base_al_dia.fetchval(
        "SELECT COUNT(*) FROM INSCRIPCIONES_TORNEO i"
        " JOIN EQUIPOS e ON e.ID = i.Equipo_ID"
        " JOIN TORNEO t ON t.ID = i.Torneo_ID"
        " WHERE e.Disciplina_ID <> t.Disciplina_ID"
    )
    assert cruzadas == 0, f"{cruzadas} inscripcion(es) de la demo con equipo de otra disciplina"


async def test_la_demo_no_usa_equipo_fantasma_para_inscripciones_individuales(base_al_dia):
    """3A-7 (docs/plans/cierre-backlog-todos-plan.md): Copa Raíces (Tenis,
    Individual) inventaba un EQUIPOS 'Micky Fernández' para poder anclar la
    inscripción vía Equipo_ID — el patrón viejo, previo a la Decisión B1
    (ediciones-catalogo-disciplinas-plan.md), que dice que Individual
    (Modalidad.tamano_equipo=1) se inscribe directo por Jugador_Perfil_ID,
    sin ninguna fila en EQUIPOS. Esta es la regresión permanente: ninguna
    inscripción de una modalidad individual debe tener Equipo_ID, y
    ninguna debe quedar sin Jugador_Perfil_ID."""
    mal_ancladas = await base_al_dia.fetchval(
        "SELECT COUNT(*) FROM INSCRIPCIONES_TORNEO i"
        " JOIN TORNEO t ON t.ID = i.Torneo_ID"
        " JOIN MODALIDAD m ON m.ID = t.Modalidad_ID"
        " WHERE m.Tamano_Equipo = 1 AND (i.Equipo_ID IS NOT NULL OR i.Jugador_Perfil_ID IS NULL)"
    )
    assert mal_ancladas == 0, (
        f"{mal_ancladas} inscripción(es) de una modalidad Individual con Equipo_ID en vez de "
        "Jugador_Perfil_ID (patrón viejo de equipo fantasma)"
    )


def test_todo_archivo_de_database_esta_clasificado():
    """F10/E-L6 test 2 (portal-publico-feed-partidos-plan.md): cobertura de
    directorio. `set(glob) - SQL_FILES - SCRIPTS_HISTORICOS - SEEDS_MANUALES`
    tiene que ser exactamente SCRIPTS_VIGENTES — si no, un script nuevo se
    agregó a /database sin decidir dónde va, y ese es el modo de falla más
    silencioso de los tres que describe C13: `SCRIPTS_VIGENTES` nunca se
    abre, el delta de columnas da 0 y todo queda verde con una migración
    que nadie corrió nunca."""
    archivos_en_disco = {p.name for p in DATABASE_DIR.glob("*.sql")}
    clasificados = set(SQL_FILES) | set(SCRIPTS_HISTORICOS) | set(SEEDS_MANUALES) | set(SCRIPTS_VIGENTES)
    sin_clasificar = archivos_en_disco - clasificados
    assert not sin_clasificar, (
        f"{sorted(sin_clasificar)} no está en SQL_FILES, SCRIPTS_VIGENTES, SCRIPTS_HISTORICOS "
        "ni SEEDS_MANUALES (test_scripts_sql.py) — agregalo a SCRIPTS_VIGENTES si tiene que "
        "correr limpio contra el esquema actual, o a SCRIPTS_HISTORICOS/SEEDS_MANUALES si no."
    )
    fantasma = clasificados - archivos_en_disco
    assert not fantasma, f"{sorted(fantasma)} está listado en test_scripts_sql.py pero no existe en /database"


@pytest_asyncio.fixture(scope="module")
async def columnas_por_tabla():
    """F10/E-L6 test 1: compara las columnas de una base armada solo con
    01-06 contra las de una base armada con 01-06 + SCRIPTS_VIGENTES. Si
    coinciden, toda columna que agrega una migración vigente ya está
    espejada en 01_schema.sql (C13) — que es exactamente lo que se rompe
    si alguien olvida ese espejo: el símbolo síntoma es
    `column "x" does not exist` en 40 suites, sin mencionar dónde arreglarlo.
    """
    DB_SOLO_BASE = "torneos_mvp_columnas_base_test"
    DB_CON_VIGENTES = "torneos_mvp_columnas_vigentes_test"

    async def _armar(nombre: str, scripts: list[str]) -> set[tuple[str, str]]:
        maint = await _connect("postgres")
        try:
            await maint.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                nombre,
            )
            await maint.execute(f'DROP DATABASE IF EXISTS "{nombre}"')
            await maint.execute(f'CREATE DATABASE "{nombre}"')
        finally:
            await maint.close()

        con = await asyncpg.connect(
            host=_url.host or "localhost", port=_url.port or 5432,
            user=_url.username, password=_url.password, database=nombre,
        )
        try:
            for filename in scripts:
                await con.execute((DATABASE_DIR / filename).read_text(encoding="utf-8"))
            filas = await con.fetch(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public'"
            )
            return {(f["table_name"], f["column_name"]) for f in filas}
        finally:
            await con.close()
            maint = await _connect("postgres")
            try:
                await maint.execute(f'DROP DATABASE IF EXISTS "{nombre}"')
            finally:
                await maint.close()

    solo_base = await _armar(DB_SOLO_BASE, SQL_FILES)
    con_vigentes = await _armar(DB_CON_VIGENTES, SQL_FILES + SCRIPTS_VIGENTES)
    return solo_base, con_vigentes


async def test_01_schema_espeja_todas_las_columnas_de_scripts_vigentes(columnas_por_tabla):
    solo_base, con_vigentes = columnas_por_tabla
    faltantes_en_01_schema = con_vigentes - solo_base
    assert not faltantes_en_01_schema, (
        f"{sorted(faltantes_en_01_schema)} existen después de correr SCRIPTS_VIGENTES pero no "
        "después de correr solo 01-06 — alguna migración de SCRIPTS_VIGENTES agrega una columna "
        "que no está espejada en 01_schema.sql (C13). Agregala ahí también."
    )
    # No debería poder pasar (una migración no borra columnas), pero si
    # pasa el mensaje tiene que decir qué, no un AssertionError pelado.
    sobrantes_en_01_schema = solo_base - con_vigentes
    assert not sobrantes_en_01_schema, (
        f"{sorted(sobrantes_en_01_schema)} existen en 01-06 pero desaparecen tras correr "
        "SCRIPTS_VIGENTES — alguna migración vigente hace DROP COLUMN de algo que 01_schema.sql declara."
    )
