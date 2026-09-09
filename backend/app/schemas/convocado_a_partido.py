from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConvocadoInput(BaseModel):
    """Una fila de la convocatoria que manda el frontend — ver
    ConvocatoriaSetRequest para el shape completo del PUT."""

    jugador_perfil_id: int
    titular: bool = False


class ConvocatoriaSetRequest(BaseModel):
    """PUT /partidos/{id}/convocados reemplaza la convocatoria ENTERA de
    ese partido de una sola vez (3B-2, docs/plans/cierre-backlog-todos-plan.md)
    — no hay POST/DELETE de una fila suelta: el flujo real es "el
    entrenador arma la lista completa antes del partido", no ir tildando
    de a uno contra el servidor. Una lista vacía es válida (saca la
    convocatoria entera, vuelve al comportamiento de siempre: toda la
    plantilla es candidata)."""

    convocados: list[ConvocadoInput]
    # ETag de concurrencia optimista (gestionar-partido-alineaciones-plan.md,
    # H4-eng): el `MAX(fecha_modificacion)` que el cliente vio al cargar la
    # convocatoria. Si en el medio la tocaron desde otro dispositivo, el service
    # responde 412 con el estado vigente en vez de pisar el trabajo del otro.
    # `None` = "no me importa", para no romper clientes que no lo mandan.
    version: datetime | None = None


class ConvocadoAgregarRequest(BaseModel):
    """POST /partidos/{id}/convocados — suma UN convocado sin tocar el resto
    (gestionar-partido-alineaciones-plan.md, D3 revisada).

    Es el camino de las llegadas tardías, y por eso es un endpoint aparte del
    PUT: al ser aditivo funciona con el partido en curso sin riesgo de pisar la
    alineación ni de perder el trabajo de otro operador. Con el partido ya
    iniciado, `titular` debe ser False — el que llega tarde entra al banco y
    pasa a cancha vía el evento Cambio."""

    jugador_perfil_id: int
    titular: bool = False
    # Minuto de partido en el que se sumó. Solo se guarda si el partido ya
    # arrancó; es el dato que le da valor probatorio al alta (H5-eng), porque
    # `fecha_registro` es el inicio de la transacción y no dice nada del juego.
    minuto_ingreso: int | None = None


class ConvocadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    partido_id: int
    jugador_perfil_id: int
    titular: bool
    fecha_registro: datetime
    # El cliente lo devuelve como `version` en el PUT siguiente — ver
    # ConvocatoriaSetRequest.version.
    fecha_modificacion: datetime | None = None
    minuto_ingreso: int | None = None
    registrado_por: int | None = None
