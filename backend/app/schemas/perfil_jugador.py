"""Perfil de Jugador: stats + trayectoria consolidadas por disciplina
(equipos-jugadores-plan.md, Fase 2, Etapa D). Solo lectura — se arma
componiendo vistas de Fase 1 (vw_estado_perfil_disciplina,
vw_goleadores_por_disciplina) y tablas reales ya mapeadas, no es un
recurso con su propio CRUD."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

EstadoPerfil = Literal["Libre", "Activo", "Suspendido"]


class EquipoActivoOut(BaseModel):
    inscripcion_torneo_id: int
    torneo_id: int
    torneo: str
    equipo_id: int
    equipo: str
    dorsal: int | None
    fecha_inicio: date


class TraspasoTrayectoriaOut(BaseModel):
    id: int
    fecha_traspaso: datetime
    # None = fichaje desde agencia libre (sin equipo de origen).
    origen: str | None
    destino: str
    motivo: str | None
    estado: Literal["Completado", "Anulado"]


class PerfilDisciplinaOut(BaseModel):
    jugador_perfil_id: int
    disciplina_id: int
    disciplina: str
    estado: EstadoPerfil
    goles_totales: int
    equipos_activos: list[EquipoActivoOut]
    trayectoria: list[TraspasoTrayectoriaOut]


class PerfilJugadorPublicOut(BaseModel):
    """Proyección sin PII para un caller anónimo — GET /jugadores/{id}/perfil
    sigue siendo público, pero ya no expone cédula/correo a cualquiera
    (ver JugadorPublicOut en app/schemas/jugador.py y
    get_current_user_optional en app/api/deps.py)."""

    jugador_id: int
    nombre: str
    foto_url: str | None = None
    disciplinas: list[PerfilDisciplinaOut]


class PerfilJugadorOut(PerfilJugadorPublicOut):
    cedula: str
    correo_electronico: str
