"""Permisos sobre los catálogos compartidos (TASK-013, SEC-04).

Decisión del propietario (2026-11-18): equipos y jugadores son un catálogo
COMPARTIDO entre organizadores. Cualquiera los crea y edita; las acciones
destructivas (baja, cambio de estado, suspensión de un perfil) afectan a
todos los torneos donde participan, así que exigen administrarlos a todos.
AdminGeneral no tiene restricción. Un equipo o jugador que no participa en
ningún torneo abierto lo puede dar de baja cualquier organizador.

"Participa en un torneo abierto": tiene una inscripción vigente (equipo) o
una membresía activa en la plantilla (jugador o perfil) de un torneo que no
está finalizado.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import ForbiddenError
from app.models.usuario import Usuario
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository

_TORNEOS_DE_EQUIPO = """
    SELECT DISTINCT it.Torneo_ID
      FROM INSCRIPCIONES_TORNEO it
      JOIN TORNEO t ON t.ID = it.Torneo_ID
     WHERE it.Equipo_ID = :id
       AND it.Estado IN ('Inscrito', 'Confirmado')
       AND t.Estado <> 'Finalizado'
"""

_TORNEOS_DE_PERFILES = """
    SELECT DISTINCT it.Torneo_ID
      FROM JUGADOR_EQUIPO je
      JOIN JUGADOR_PERFIL_DISCIPLINA jpd ON jpd.ID = je.Jugador_Perfil_ID
      JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
      JOIN TORNEO t ON t.ID = it.Torneo_ID
     WHERE {filtro}
       AND je.Estado = 'Activo'
       AND t.Estado <> 'Finalizado'
"""


async def _torneos(session: AsyncSession, sql: str, id_: int) -> set[int]:
    result = await session.execute(text(sql), {"id": id_})
    return set(result.scalars().all())


async def _exigir_todos_administrados(
    usuario: Usuario, torneo_ids: set[int], session: AsyncSession, que: str
) -> None:
    if usuario.rol == "AdminGeneral" or not torneo_ids:
        return
    asignados = set(await AsignacionTorneoAdminRepository(session).listar_torneo_ids_activos(usuario.id))
    if not torneo_ids <= asignados:
        raise ForbiddenError(
            f"{que} participa en torneos que no administrás. Solo quien administra todos esos torneos "
            "(o un Admin General) puede hacer esta operación."
        )


async def exigir_admin_de_torneos_del_equipo(usuario: Usuario, equipo_id: int, session: AsyncSession) -> None:
    await _exigir_todos_administrados(
        usuario, await _torneos(session, _TORNEOS_DE_EQUIPO, equipo_id), session, "Este equipo"
    )


async def exigir_admin_de_torneos_del_jugador(usuario: Usuario, jugador_id: int, session: AsyncSession) -> None:
    sql = _TORNEOS_DE_PERFILES.format(filtro="jpd.Jugador_ID = :id")
    await _exigir_todos_administrados(usuario, await _torneos(session, sql, jugador_id), session, "Este jugador")


async def exigir_admin_de_torneos_del_perfil(usuario: Usuario, perfil_id: int, session: AsyncSession) -> None:
    sql = _TORNEOS_DE_PERFILES.format(filtro="jpd.ID = :id")
    await _exigir_todos_administrados(usuario, await _torneos(session, sql, perfil_id), session, "Este jugador")


async def exigir_admin_del_grupo(usuario: Usuario, torneo_grupo_id: int, session: AsyncSession) -> None:
    """Un grupo de torneos lo modifica quien administra alguna de sus
    ediciones (renombrarlo o archivarlo alcanza a todas). Quien crea un
    torneo recibe su asignación, así que sigue pudiendo renombrar su grupo."""
    if usuario.rol == "AdminGeneral":
        return
    result = await session.execute(
        text("SELECT ID FROM TORNEO WHERE Torneo_Grupo_ID = :id"), {"id": torneo_grupo_id}
    )
    ediciones = set(result.scalars().all())
    asignados = set(await AsignacionTorneoAdminRepository(session).listar_torneo_ids_activos(usuario.id))
    if not ediciones & asignados:
        raise ForbiddenError(
            "No administrás ninguna edición de este grupo de torneos. Pedile a tu Admin General que te "
            "asigne una."
        )
