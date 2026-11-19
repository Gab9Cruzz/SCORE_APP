"""Regla única de alta en plantilla (TASK-017, FUN-08/FUN-15).

Antes el tope de plantilla y la comprobación de suspensión solo existían en
el registro por lote: el alta individual, el traspaso y la copia de la
plantilla base dejaban pasar a un suspendido o pasarse del tope. Los cuatro
caminos llaman a `validar_alta` antes de crear la membresía.

Los mensajes son los mismos que ya mostraba el lote, para que el usuario vea
lo mismo venga por donde venga.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError, NotFoundError
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.modalidad import Modalidad
from app.models.torneo import Torneo
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository

MENSAJE_SUSPENDIDO = "Jugador suspendido en esta disciplina"


def tope_de_plantilla(modalidad: Modalidad) -> int | None:
    """3B-4 (docs/plans/cierre-backlog-todos-plan.md): el tope real de esta
    modalidad — `Tamano_Plantilla_Max` si el catálogo lo trae seteado (equipo
    grande con un roster máximo explícito, ej. Fútbol 11=25), si no el mismo
    criterio de siempre para Pareja (`tamano_equipo<=2`, EC-6). Para un
    equipo grande SIN `Tamano_Plantilla_Max` seteado, no hay tope."""
    if modalidad.tamano_plantilla_max is not None:
        return modalidad.tamano_plantilla_max
    if modalidad.tamano_equipo <= 2:
        return modalidad.tamano_equipo
    return None


def mensaje_tope(tope: int) -> str:
    return f"Esta modalidad admite máximo {tope} jugadores por equipo"


async def validar_alta(
    session: AsyncSession, *, jugador_perfil_id: int, inscripcion: InscripcionTorneo, torneo: Torneo
) -> None:
    """Perfil de la disciplina del torneo, no suspendido, jugador activo y
    lugar en la plantilla (con el mismo bloqueo que el lote, para que dos
    altas concurrentes no tomen el último lugar las dos)."""
    perfil = await session.get(JugadorPerfilDisciplina, jugador_perfil_id)
    if perfil is None:
        raise NotFoundError("JugadorPerfilDisciplina", jugador_perfil_id)
    if perfil.disciplina_id != torneo.disciplina_id:
        raise DomainRuleError("Ese perfil de jugador es de otra disciplina que la del torneo.")
    if perfil.suspendido:
        raise DomainRuleError(MENSAJE_SUSPENDIDO)
    jugador = await session.get(Jugador, perfil.jugador_id)
    if jugador is not None and jugador.estado != "Activo":
        raise DomainRuleError("El jugador está dado de baja: reactivalo antes de sumarlo a una plantilla.")

    if torneo.modalidad_id is None:
        return
    modalidad = await session.get(Modalidad, torneo.modalidad_id)
    tope = tope_de_plantilla(modalidad) if modalidad is not None else None
    if tope is None:
        return
    await InscripcionTorneoRepository(session).lock_cupo_inscripcion(inscripcion.id)
    activos = (
        await session.execute(
            select(func.count())
            .select_from(JugadorEquipo)
            .where(JugadorEquipo.inscripcion_torneo_id == inscripcion.id, JugadorEquipo.estado == "Activo")
        )
    ).scalar_one()
    if activos >= tope:
        raise DomainRuleError(mensaje_tope(tope))
