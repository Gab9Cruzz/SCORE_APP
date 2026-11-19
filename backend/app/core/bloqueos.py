"""Bloqueos consultivos de transacción, con espacio de claves por uso
(TASK-024, BE-09/DB-05).

Antes cada uso tomaba `pg_advisory_xact_lock(id)` con su propio id: el cupo
del torneo 5, el de la inscripción 5 y el número de edición del grupo 5
compartían la misma clave y se esperaban entre sí sin motivo. Ahora todos
usan la forma de dos claves `(espacio, id)`, con un espacio fijo por uso.
Los bloqueos se liberan solos al terminar la transacción.
"""
from enum import IntEnum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class Espacio(IntEnum):
    """No reutilizar ni renumerar: dos usos con el mismo número volverían a
    compartir claves."""

    CUPO_TORNEO = 1  # alta de inscripciones contra Cupo_Maximo_Inscripciones
    CUPO_INSCRIPCION = 2  # altas en la plantilla de una inscripción (tope)
    NUMERO_EDICION = 3  # siguiente edición de un grupo de torneos
    EXCLUSIVIDAD_PERFIL = 4  # un perfil activo en un solo equipo por torneo
    MOTOR_FORMATOS = 5  # sorteo, fixture y playoffs de un torneo


async def bloquear(session: AsyncSession, espacio: Espacio, id_: int) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:espacio, :id)"), {"espacio": int(espacio), "id": id_}
    )
