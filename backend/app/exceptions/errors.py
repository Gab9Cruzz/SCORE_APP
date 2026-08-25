"""Excepciones de dominio.

Los repositorios las lanzan; app/exceptions/handlers.py las traduce a
respuestas JSON. Así los servicios no dependen de FastAPI y los routers no
repiten try/except.
"""


class NotFoundError(Exception):
    """El recurso pedido no existe (o está borrado lógicamente y no aplica)."""

    def __init__(self, recurso: str, id_: int | str):
        self.detail = f"{recurso} con id={id_} no encontrado."
        super().__init__(self.detail)


class ConflictError(Exception):
    """Viola una restricción UNIQUE (ej: dorsal repetido, torneo duplicado)."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(self.detail)


class DomainRuleError(Exception):
    """Regla de negocio violada.

    Cubre tanto CHECK constraints de Postgres como las excepciones que
    lanzan los triggers en 06_triggers.sql (ej: "El jugador no pertenecia
    a ese equipo en la fecha del partido."). El mensaje que llega desde la
    base ya es legible en español, así que se reusa tal cual.
    """

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(self.detail)


class AuthError(Exception):
    """Credenciales inválidas o token ausente/expirado."""

    def __init__(self, detail: str = "No autenticado."):
        self.detail = detail
        super().__init__(self.detail)


class ForbiddenError(Exception):
    """Usuario autenticado pero sin el rol requerido para la operación."""

    def __init__(self, detail: str = "No tenés permiso para esta operación."):
        self.detail = detail
        super().__init__(self.detail)
