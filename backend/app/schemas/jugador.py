from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas._tipos import Cedula, Correo, Nombre100, UrlHttps

EstadoJugador = Literal["Activo", "Inactivo"]


class JugadorBase(BaseModel):
    nombre: str
    cedula: str
    # NO es único a nivel de API tampoco (EC-12 del plan, ver
    # unique_jugador_cedula en 02_constraints.sql — el UNIQUE es solo sobre
    # cedula): dos cédulas distintas pueden compartir un correo familiar.
    correo_electronico: str


class JugadorCreate(JugadorBase):
    # TASK-029: validación de entrada (la de JugadorBase la comparte la salida).
    nombre: Nombre100
    cedula: Cedula
    correo_electronico: Correo
    pass


class JugadorUpdate(BaseModel):
    nombre: Nombre100 | None = None
    cedula: Cedula | None = None
    correo_electronico: Correo | None = None
    estado: EstadoJugador | None = None
    foto_url: UrlHttps | None = None  # TASK-029 (SEC-11): como los logos


class JugadorOut(JugadorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoJugador
    foto_url: str | None = None
    fecha_registro: datetime
    fecha_modificacion: datetime


class JugadorPublicOut(BaseModel):
    """Proyección sin PII (sin cédula ni correo) para un caller anónimo —
    los GET de jugadores() siguen siendo públicos (no exigen login), pero
    ya no filtran cédula/correo a cualquiera. Un caller autenticado (el
    admin logueado del frontend, que ya manda el Bearer token en cada
    request) sigue recibiendo JugadorOut completo en la misma ruta — ver
    get_current_user_optional en app/api/deps.py.

    foto_url SÍ va acá (a diferencia de cédula/correo): es del mismo nivel
    de exposición que `nombre`, y el grid de Plantillas la necesita para
    mostrar la tarjeta de cada jugador."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    estado: EstadoJugador
    foto_url: str | None = None
