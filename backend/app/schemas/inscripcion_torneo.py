from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

EstadoInscripcion = Literal["Inscrito", "Cancelado", "Confirmado"]


class InscripcionTorneoCreate(BaseModel):
    """Exactamente uno de los dos caminos (ediciones-catalogo-disciplinas-plan.md,
    Decisión B1):
    - `equipo_id`: Pareja/Conjunto (Modalidad.tamano_equipo >= 2) — un
      equipo ya existente se inscribe tal cual (sin cambios de acá).
    - `jugador_cedula`/`jugador_nombre`/`jugador_correo_electronico`:
      Individual (Modalidad.tamano_equipo == 1) — resuelve-o-crea el
      Jugador + su perfil de disciplina (mismo camino que
      RegistroLoteService, D-Eng-6) y NO crea ninguna fila en EQUIPOS."""

    torneo_id: int
    equipo_id: int | None = None
    jugador_cedula: str | None = None
    jugador_nombre: str | None = None
    jugador_correo_electronico: str | None = None

    @model_validator(mode="after")
    def exactamente_un_camino(self):
        tiene_equipo = self.equipo_id is not None
        tiene_jugador = bool(self.jugador_cedula and self.jugador_cedula.strip())
        if tiene_equipo == tiene_jugador:  # ambos True o ambos False
            raise ValueError(
                "Mandá exactamente uno: equipo_id (Pareja/Conjunto) o "
                "jugador_cedula + jugador_nombre + jugador_correo_electronico (Individual)."
            )
        if tiene_jugador and not (
            self.jugador_nombre
            and self.jugador_nombre.strip()
            and self.jugador_correo_electronico
            and self.jugador_correo_electronico.strip()
        ):
            raise ValueError(
                "jugador_nombre y jugador_correo_electronico son obligatorios junto con jugador_cedula."
            )
        return self


class InscripcionTorneoUpdate(BaseModel):
    estado: EstadoInscripcion


class InscripcionTorneoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    torneo_id: int
    # Exactamente uno de los dos — chk_inscripcion_exactamente_uno
    # (02_constraints.sql). Nunca "equipo" en el mensaje/UI cuando es
    # individual: no reintroducir el concepto que el usuario pidió omitir.
    equipo_id: int | None
    jugador_perfil_id: int | None
    estado: EstadoInscripcion
    fecha: datetime
    fecha_registro: datetime
    fecha_modificacion: datetime
