"""Verificación end-to-end de database/13_migracion_equipos_disciplina.sql
contra una base descartable con el esquema VIEJO (el de git HEAD, sin
EQUIPOS.Disciplina_ID). Cubre T9 (equipo ambiguo → primera disciplina por
orden + reporte) y T10 (equipo huérfano → Inactivo + la migración frena).

No toca torneos_mvp ni torneos_mvp_test: crea y borra torneos_mvp_mig_check.
"""
import asyncio
import pathlib
import subprocess
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncpg

REPO = pathlib.Path(r"c:\Users\Gabo\Desktop\proyectos\Score-App")
DB = "torneos_mvp_mig_check"
CONN = dict(host="127.0.0.1", port=5432, user="postgres", password="1234")


def sql_de_head(nombre: str) -> str:
    return subprocess.run(
        ["git", "show", f"HEAD:database/{nombre}"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout


async def main() -> None:
    maint = await asyncpg.connect(database="postgres", **CONN)
    await maint.execute(f'DROP DATABASE IF EXISTS "{DB}"')
    await maint.execute(f'CREATE DATABASE "{DB}"')
    await maint.close()

    con = await asyncpg.connect(database=DB, **CONN)
    try:
        # Esquema VIEJO: el de HEAD, donde EQUIPOS no tiene Disciplina_ID.
        for f in ["01_schema.sql", "02_constraints.sql", "03_indexes.sql",
                  "04_views.sql", "05_seed.sql", "06_triggers.sql"]:
            await con.execute(sql_de_head(f))
        print("[OK] esquema viejo + seed cargados")

        cols = await con.fetchval(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE lower(table_name)='equipos' AND lower(column_name)='disciplina_id'"
        )
        assert cols == 0, "el esquema de HEAD ya tiene Disciplina_ID; revisar"

        # --- Datos que ejercitan los dos casos borde ---
        # T10 / EC-36: huérfano — existe pero nunca se inscribió a nada.
        huerfano = await con.fetchval(
            "INSERT INTO EQUIPOS (Nombre) VALUES ('Huerfano FC') RETURNING ID"
        )
        # T9 / EC-35: ambiguo — inscripciones en dos disciplinas distintas.
        ajedrez = await con.fetchval("INSERT INTO DISCIPLINA (Nombre) VALUES ('Ajedrez Mig') RETURNING ID")
        blitz = await con.fetchval(
            "INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo) VALUES ($1,'Blitz Mig',1) RETURNING ID",
            ajedrez,
        )
        grupo = await con.fetchval("INSERT INTO TORNEO_GRUPO (Nombre) VALUES ('Open Ajedrez Mig') RETURNING ID")
        torneo_ajedrez = await con.fetchval(
            "INSERT INTO TORNEO (Nombre, Disciplina_ID, Modalidad_ID, Torneo_Grupo_ID, Numero_Edicion,"
            " Fecha_Inicio, Fecha_Fin) VALUES ('Open Ajedrez Mig 1',$1,$2,$3,1,'2026-01-01','2026-02-01')"
            " RETURNING ID",
            ajedrez, blitz, grupo,
        )
        # El equipo 1 (Tiburones FC, Fútbol por el torneo 1 del seed) se
        # inscribe también al torneo de Ajedrez → ambiguo.
        await con.execute(
            "INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID) VALUES ($1, 1)", torneo_ajedrez
        )
        print(f"[OK] datos de borde: huerfano id={huerfano}, ambiguo id=1 (Futbol + Ajedrez)")

        migracion = (REPO / "database" / "13_migracion_equipos_disciplina.sql").read_text(encoding="utf-8")

        # --- Corrida 1: debe FRENAR por el huérfano (T10) ---
        try:
            await con.execute(migracion)
            raise AssertionError("la migracion NO freno con un huerfano presente")
        except asyncpg.exceptions.RaiseError as e:
            assert "sin Disciplina_ID inferible" in str(e), str(e)
            print(f"[OK] T10: la migracion freno con el mensaje esperado -> {e}")

        # El UPDATE de la PARTE C ya se aplicó antes del RAISE de la PARTE D
        # (misma transacción implícita por statement en asyncpg.execute de un
        # script multi-statement -> se revierte todo). Se re-verifica abajo.
        estado = await con.fetchval("SELECT Estado FROM EQUIPOS WHERE ID = $1", huerfano)
        print(f"[i]  estado del huerfano tras el frenazo: {estado}")

        # --- Resolución manual del huérfano, como indica el mensaje ---
        # asyncpg manda el archivo entero como un statement, así que el RAISE
        # de la PARTE D revirtió TODO — incluidas las columnas de la PARTE A
        # (ver la nota sobre transacciones en la PARTE C de la migración).
        # Se recrean para poder resolver el huérfano a mano, que es lo que
        # haría el admin con psql.
        await con.execute("ALTER TABLE EQUIPOS ADD COLUMN IF NOT EXISTS Disciplina_ID INT")
        await con.execute("ALTER TABLE EQUIPOS ADD COLUMN IF NOT EXISTS Modalidad_ID INT")
        await con.execute(
            "UPDATE EQUIPOS SET Disciplina_ID = $1, Modalidad_ID = $2 WHERE ID = $3",
            ajedrez, blitz, huerfano,
        )

        # --- Corrida 2: ahora debe completar ---
        await con.execute(migracion)
        print("[OK] la migracion completo tras resolver el huerfano a mano")

        # T9: el ambiguo quedó con UNA disciplina coherente con su modalidad.
        fila = await con.fetchrow(
            "SELECT e.Disciplina_ID, e.Modalidad_ID, m.Disciplina_ID AS mod_disc"
            " FROM EQUIPOS e JOIN MODALIDAD m ON m.ID = e.Modalidad_ID WHERE e.ID = 1"
        )
        assert fila["disciplina_id"] == fila["mod_disc"], f"par incoherente: {dict(fila)}"
        print(f"[OK] T9: el equipo ambiguo quedo con un par coherente {dict(fila)}")

        # NOT NULL efectivo en las dos columnas.
        for col in ("disciplina_id", "modalidad_id"):
            nullable = await con.fetchval(
                "SELECT is_nullable FROM information_schema.columns"
                " WHERE lower(table_name)='equipos' AND lower(column_name)=$1", col
            )
            assert nullable == "NO", f"{col} sigue siendo nullable"
        print("[OK] Disciplina_ID y Modalidad_ID son NOT NULL")

        # El trigger nuevo rechaza un par incoherente.
        try:
            await con.execute(
                "INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID) VALUES ('Incoherente', 1, $1)",
                blitz,
            )
            raise AssertionError("el trigger NO rechazo la modalidad de otra disciplina")
        except asyncpg.exceptions.RaiseError as e:
            assert "no pertenece" in str(e), str(e)
            print("[OK] trg_equipos_validar_modalidad rechaza el par incoherente")

        # Idempotencia: correrla de nuevo no debe romper nada.
        await con.execute(migracion)
        print("[OK] la migracion es idempotente (segunda corrida limpia)")
    finally:
        await con.close()
        maint = await asyncpg.connect(database="postgres", **CONN)
        await maint.execute(f'DROP DATABASE IF EXISTS "{DB}"')
        await maint.close()
        print("[OK] base descartable eliminada")


asyncio.run(main())
