"""Script de prueba de estrés del catálogo maestro
(docs/plans/ediciones-catalogo-disciplinas-plan.md, sección "Mock Data de
Estrés"): un torneo por cada una de las 66 Modalidades del catálogo (no 28
por Disciplina — ver la "Nota de alcance" del plan: probar solo por
disciplina dejaría sin ejercitar la mitad de las combinaciones Individual/
Pareja/Conjunto que introdujo este módulo), con 10 inscripciones cada uno.

Por qué llama al service layer (TorneoService, InscripcionTorneoService,
RegistroLoteService) en vez de INSERT crudo: el propósito explícito es
ejercitar la rama Individual/Pareja/Conjunto de verdad — un INSERT directo
no dispara chk_inscripcion_exactamente_uno, fn_validar_exclusividad_torneo
ni la resolución de JUGADORES por cédula desde el mismo camino que usaría
un admin real, solo poblaría filas.

Requiere: 11_catalogo_disciplinas.sql y 12_migracion_catalogo_disciplinas.sql
ya aplicados contra la base que apunta DATABASE_URL (Modalidad_ID
obligatorio en TORNEO, INSCRIPCIONES_TORNEO admite Jugador_Perfil_ID) — si
el catálogo todavía no está cargado, el script no encuentra ninguna
Modalidad y termina sin hacer nada.

Uso (desde backend/, con el venv activado):
    python -m scripts.mock_estres_catalogo

Idempotente:
  - Cédulas determinísticas (MOCK-{modalidad_id}-...) — una segunda
    corrida reconoce los mismos jugadores por cédula en vez de duplicarlos.
  - Nombre de TORNEO_GRUPO determinístico ("Prueba de Estrés — {disciplina}
    {modalidad}") — si ya existe, se reusa su edición en vez de crear un
    torneo nuevo.
  - Si un torneo ya tiene >= 10 inscripciones (de una corrida anterior), se
    saltea entero — evita duplicar Equipos (EQUIPOS.Nombre no es único a
    nivel de esquema, así que un segundo alta con el mismo nombre generado
    sería una fila nueva, no una reutilizada).
  - Una fila que ya estaba inscripta en ese torneo (exclusividad, EC-27) se
    detecta y se saltea sin abortar el resto de la corrida.

Sin limpieza al final: la data queda cargada a propósito, para navegarla en
la UI después — filtrable/borrable en bloque por el prefijo 'MOCK-' en
Cedula y 'Prueba de Estrés — ' en el nombre del TORNEO_GRUPO.
"""
import asyncio
import sys
from datetime import date, timedelta

if sys.platform == "win32":
    # El driver de la app es psycopg (async), que se niega a correr sobre
    # ProactorEventLoop (el default de asyncio en Windows) — mismo fix que
    # tests/conftest.py, tiene que ir antes de crear cualquier event loop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.database import async_session_factory
from app.exceptions.errors import DomainRuleError
from app.models.disciplina import Disciplina
from app.models.modalidad import Modalidad
from app.models.usuario import Usuario
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.torneo import TorneoRepository
from app.repositories.torneo_grupo import TorneoGrupoRepository
from app.schemas.equipo import EquipoCreate
from app.schemas.inscripcion_torneo import InscripcionTorneoCreate
from app.schemas.registro_lote import RegistroLoteFila
from app.schemas.torneo import TorneoCreate
from app.services.equipo import EquipoService
from app.services.inscripcion_torneo import InscripcionTorneoService
from app.services.registro_lote import RegistroLoteService
from app.services.torneo import TorneoService

N_INSCRIPCIONES_POR_TORNEO = 10
PREFIJO_GRUPO = "Prueba de Estrés — "
DOMINIO_CORREO = "stress.test"

HOY = date.today()
FECHA_FIN = HOY + timedelta(days=30)


class Reporte:
    """Acumula lo que hizo el script para el resumen final — ver el
    docstring del módulo: un fallo de validación acá es señal de un bug
    real en el modelo, no un dato mal cargado, así que se lista aparte de
    los "saltados" (esperados en una segunda corrida)."""

    def __init__(self, total_modalidades: int) -> None:
        self.total_modalidades = total_modalidades
        self.torneos_creados = 0
        self.torneos_reusados = 0
        self.torneos_ya_completos = 0
        self.inscripciones_creadas = 0
        self.inscripciones_saltadas = 0
        self.fallas: list[str] = []

    def imprimir(self) -> None:
        print("\n=== Reporte final ===")
        print(f"Modalidades procesadas: {self.total_modalidades}")
        print(f"  torneos creados:                                             {self.torneos_creados}")
        print(f"  torneos reusados (grupo ya existía de una corrida anterior): {self.torneos_reusados}")
        print(f"  torneos ya completos (>= {N_INSCRIPCIONES_POR_TORNEO} inscripciones, salteados enteros): {self.torneos_ya_completos}")
        print(f"Inscripciones creadas: {self.inscripciones_creadas}")
        print(f"Inscripciones ya existentes, salteadas: {self.inscripciones_saltadas}")
        if self.fallas:
            print(f"\n{len(self.fallas)} fila(s) fallaron validación (revisar — señal de un bug real, no de dato mal cargado):")
            for f in self.fallas:
                print(f"  - {f}")
        else:
            print("\nSin fallas de validación.")


async def cargar_catalogo(session) -> list[tuple[Disciplina, Modalidad]]:
    stmt = (
        select(Disciplina, Modalidad)
        .join(Modalidad, Modalidad.disciplina_id == Disciplina.id)
        .order_by(Disciplina.nombre, Modalidad.nombre)
    )
    result = await session.execute(stmt)
    return [(d, m) for d, m in result.all()]


def cedula_individual(modalidad_id: int, i: int) -> str:
    return f"MOCK-{modalidad_id:03d}-{i:02d}"


def cedula_de_equipo(modalidad_id: int, equipo_idx: int, jugador_idx: int) -> str:
    return f"MOCK-{modalidad_id:03d}-{equipo_idx:02d}-{jugador_idx:02d}"


async def obtener_o_crear_torneo(
    session, disciplina: Disciplina, modalidad: Modalidad, reporte: Reporte
) -> tuple[int, int]:
    """Devuelve (torneo_id, cuántas inscripciones ya tiene) — reusa el
    TORNEO_GRUPO si ya existe (nombre determinístico) en vez de crear uno
    nuevo cada corrida."""
    nombre_grupo = f"{PREFIJO_GRUPO}{disciplina.nombre} {modalidad.nombre}"
    grupo_repo = TorneoGrupoRepository(session)
    torneo_repo = TorneoRepository(session)
    inscripcion_repo = InscripcionTorneoRepository(session)

    existentes = await grupo_repo.list(nombre=nombre_grupo, limit=1)
    if existentes:
        grupo = existentes[0]
        ediciones = await torneo_repo.listar_ediciones_del_grupo(grupo.id)
        torneo_id = ediciones[0].id  # una sola edición por diseño de este script
        reporte.torneos_reusados += 1
    else:
        torneo = await TorneoService(session).create(
            TorneoCreate(
                disciplina_id=disciplina.id,
                modalidad_id=modalidad.id,
                torneo_grupo_nombre=nombre_grupo,
                fecha_inicio=HOY,
                fecha_fin=FECHA_FIN,
            ),
            # AdminGeneral "de mentira" (no persistido — rbac-licencias-torneos-plan.md,
            # D4): este script de datos de prueba no tiene un actor logueado
            # real; AdminGeneral no genera fila de asignación (bypass total).
            Usuario(rol="AdminGeneral"),
        )
        torneo_id = torneo.id
        reporte.torneos_creados += 1

    inscripciones_actuales = await inscripcion_repo.list(torneo_id=torneo_id, limit=200)
    return torneo_id, len(inscripciones_actuales)


async def cargar_individuales(session, torneo_id: int, modalidad: Modalidad, reporte: Reporte) -> None:
    inscripcion_service = InscripcionTorneoService(session)
    for i in range(1, N_INSCRIPCIONES_POR_TORNEO + 1):
        cedula = cedula_individual(modalidad.id, i)
        data = InscripcionTorneoCreate(
            torneo_id=torneo_id,
            jugador_cedula=cedula,
            jugador_nombre=f"Jugador Genérico {i}",
            jugador_correo_electronico=f"mock{modalidad.id}.{i}@{DOMINIO_CORREO}",
        )
        try:
            await inscripcion_service.create(data)
            reporte.inscripciones_creadas += 1
        except (IntegrityError, DBAPIError) as e:
            await session.rollback()
            mensaje = str(getattr(e, "orig", e) or e)
            if "unique_inscripcion_individual" in mensaje or "jugador_ya_activo_en_este_torneo" in mensaje:
                reporte.inscripciones_saltadas += 1
            else:
                reporte.fallas.append(f"Modalidad {modalidad.id} ({modalidad.nombre}) individual #{i}: {mensaje}")
        except DomainRuleError as e:
            # Sin escritura en la base (se revienta antes del flush) — no
            # hace falta rollback, pero sí registrar la falla.
            reporte.fallas.append(f"Modalidad {modalidad.id} ({modalidad.nombre}) individual #{i}: {e.detail}")


async def cargar_equipos(
    session, torneo_id: int, disciplina: Disciplina, modalidad: Modalidad, reporte: Reporte
) -> None:
    equipo_service = EquipoService(session)
    inscripcion_service = InscripcionTorneoService(session)
    registro_lote_service = RegistroLoteService(session)

    for e in range(1, N_INSCRIPCIONES_POR_TORNEO + 1):
        jugadores = [
            {
                "cedula": cedula_de_equipo(modalidad.id, e, j),
                "nombre": f"Jugador {e}.{j}",
                "correo_electronico": f"mock{modalidad.id}.{e}.{j}@{DOMINIO_CORREO}",
            }
            for j in range(1, modalidad.tamano_equipo + 1)
        ]
        nombre_equipo = (
            " / ".join(j["nombre"] for j in jugadores[:2])  # Decisión D
            if modalidad.tamano_equipo == 2
            else f"Equipo Genérico {e} — {disciplina.nombre}"
        )

        try:
            equipo = await equipo_service.create(EquipoCreate(nombre=nombre_equipo))
            inscripcion = await inscripcion_service.create(
                InscripcionTorneoCreate(torneo_id=torneo_id, equipo_id=equipo.id)
            )
        except (IntegrityError, DBAPIError) as ex:
            await session.rollback()
            reporte.fallas.append(
                f"Modalidad {modalidad.id} ({modalidad.nombre}) equipo #{e}: no se pudo crear/inscribir — "
                f"{getattr(ex, 'orig', ex) or ex}"
            )
            continue

        filas = [
            RegistroLoteFila(
                cedula=j["cedula"], nombre=j["nombre"], correo_electronico=j["correo_electronico"], dorsal=dorsal
            )
            for dorsal, j in enumerate(jugadores, start=1)
        ]
        insertados, rechazados = await registro_lote_service.confirmar(
            inscripcion_torneo_id=inscripcion.id, fecha_inicio=HOY, filas=filas
        )
        reporte.inscripciones_creadas += 1  # cuenta el equipo/pareja como una "inscripción"
        for r in rechazados:
            # EC-18 de RegistroLoteService: "Ya juega en {equipo} este
            # torneo..." — el conflicto esperado en una segunda corrida
            # (mismas cédulas, mismo torneo).
            if "ya juega en" in r.motivo.lower():
                reporte.inscripciones_saltadas += 1
            else:
                reporte.fallas.append(
                    f"Modalidad {modalidad.id} ({modalidad.nombre}) equipo #{e}, {r.nombre}: {r.motivo}"
                )


async def main() -> None:
    async with async_session_factory() as session:
        catalogo = await cargar_catalogo(session)
        if not catalogo:
            print(
                "El catálogo está vacío — corré 11_catalogo_disciplinas.sql "
                "(y 12_migracion_catalogo_disciplinas.sql si esta base ya estaba provisionada) antes de este script."
            )
            return
        reporte = Reporte(total_modalidades=len(catalogo))
        print(f"Catálogo cargado: {len(catalogo)} modalidad(es) — {N_INSCRIPCIONES_POR_TORNEO} inscripciones cada una.")

        for disciplina, modalidad in catalogo:
            torneo_id, ya_inscriptos = await obtener_o_crear_torneo(session, disciplina, modalidad, reporte)

            # Idempotencia a nivel de TORNEO (todo o nada), no fila por
            # fila: en el camino de Equipo, un torneo con 0 < inscriptos <
            # N (interrumpido a mitad de una corrida anterior, ej. Ctrl+C)
            # NO se detecta acá y el loop de abajo generaría equipos
            # nuevos en vez de completar los que faltaban — EQUIPOS.Nombre
            # no es único a nivel de esquema, así que no hay forma barata
            # de saber "el equipo #7 de esta modalidad ya existe" sin
            # guardar ese mapeo aparte. Aceptable para un script de
            # prueba de estrés: correrlo de nuevo sin interrupciones deja
            # cada torneo en 10 igual, solo con algunos equipos "de más"
            # con roster completo si hubo una corrida parcial en el medio.
            if ya_inscriptos >= N_INSCRIPCIONES_POR_TORNEO:
                reporte.torneos_ya_completos += 1
                reporte.inscripciones_saltadas += N_INSCRIPCIONES_POR_TORNEO
                continue

            if modalidad.tamano_equipo == 1:
                await cargar_individuales(session, torneo_id, modalidad, reporte)
            else:
                await cargar_equipos(session, torneo_id, disciplina, modalidad, reporte)

    reporte.imprimir()


if __name__ == "__main__":
    asyncio.run(main())
