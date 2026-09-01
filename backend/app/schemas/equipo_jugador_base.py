from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoEquipoJugadorBase = Literal["Activo", "Inactivo"]


class EquipoJugadorBaseCreate(BaseModel):
    """Agrega un candidato a la Plantilla Base de un equipo
    (gestion-avanzada-equipos-control-mesa-plan.md, D1-C). `jugador_id`
    (no `jugador_perfil_id`): el buscador de la UI trabaja con Jugador
    (nombre/cédula), el service resuelve-o-crea el
    JugadorPerfilDisciplina para la disciplina DEL EQUIPO — mismo patrón
    que InscripcionTorneoService._crear_individual."""

    jugador_id: int
    dorsal_sugerido: int | None = None


class EquipoJugadorBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipo_id: int
    jugador_perfil_id: int
    # Denormalizados desde Jugador vía el perfil — la tabla de la UI
    # ("Cédula | Nombre | Dorsal sugerido | Quitar") los necesita directo,
    # sin que el frontend tenga que resolver el perfil por su cuenta.
    jugador_id: int
    jugador_nombre: str
    jugador_cedula: str
    dorsal_sugerido: int | None
    estado: EstadoEquipoJugadorBase
    fecha_registro: datetime
    fecha_modificacion: datetime


class ConflictoMultimilitancia(BaseModel):
    """Resultado de GET /equipos/{id}/plantilla-base/verificar — Nivel 1
    del Algoritmo de Multimilitancia del plan: global, nunca bloqueante.
    El mensaje es el texto literal pedido por el usuario (Flujo 2 del
    plan) — no se resume ni se genera de otra forma."""

    conflicto: bool
    equipos: list[str] = []
    mensaje: str | None = None
