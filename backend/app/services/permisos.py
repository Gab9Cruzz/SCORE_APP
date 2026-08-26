"""Ownership-check de Árbitro: "¿este partido es tuyo?"

Vive acá, en el Service, no como FastAPI dependency (roles-3-modulos-plan.md,
Fase 1, D5) — PartidoService.update() y EventoPartidoService.create()/anular()
ya necesitan cargar el Partido para operar (o para el chequeo mismo), así
que esto se llama desde ahí en vez de agregar una consulta aparte a nivel
de router.

TorneoAdmin y AdminGeneral nunca pasan por acá con una restricción real:
require_roles() (app/api/deps.py) ya decide quién llega al Service. Esta
función solo hace algo cuando el rol es Arbitro.
"""
from app.exceptions.errors import ForbiddenError
from app.models.partido import Partido
from app.models.usuario import Usuario


def verificar_arbitro_asignado(partido: Partido, usuario: Usuario) -> None:
    """Si `usuario` es Arbitro, exige que sea EL árbitro asignado a `partido`."""
    if usuario.rol != "Arbitro":
        return
    if partido.arbitro_id != usuario.id:
        raise ForbiddenError("Este partido no está asignado a vos.")
