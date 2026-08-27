from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JugadorPerfilDisciplinaCreate(BaseModel):
    jugador_id: int
    disciplina_id: int


class JugadorPerfilDisciplinaUpdate(BaseModel):
    # Único campo mutable: no tiene Estado (ver el modelo — el estado
    # Libre/Activo se deriva, no se guarda). Sancionar/levantar sanción es
    # la única escritura manual que tiene sentido acá.
    suspendido: bool | None = None


class JugadorPerfilDisciplinaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    jugador_id: int
    disciplina_id: int
    suspendido: bool
    fecha_registro: datetime
    fecha_modificacion: datetime
