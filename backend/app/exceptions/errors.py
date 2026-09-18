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


class LicenseRevokedError(ForbiddenError):
    """Usuario autenticado, credenciales válidas, pero sin licencia activa
    (rbac-licencias-torneos-plan.md). 403 (no 401): la identidad SÍ es
    válida, lo que falta es autorización de nivel superior — mismo
    criterio que separa AuthError de ForbiddenError en este archivo.

    Handler (`exceptions/handlers.py`) agrega el header `X-License-Revoked`
    para que el frontend distinga esto de un 403 genérico sin parsear el
    body — mismo patrón que RateLimitError usa `Retry-After` más abajo."""

    def __init__(self, detail: str = "Licencia inactiva o revocada. Contactá al administrador."):
        super().__init__(detail)


class PreconditionFailedError(Exception):
    """Conflicto de concurrencia optimista: el recurso cambió entre el GET y el
    PUT (gestionar-partido-alineaciones-plan.md, H3-eng).

    412 y no 409 a propósito. `handlers.py` ya mapea TODO `IntegrityError` a
    409, así que un 409 nuevo sería indistinguible para el cliente de una
    violación de unicidad — y en la convocatoria las dos cosas pasan en el mismo
    endpoint (`unique_convocado_partido` choca con el doble-tap). El frontend
    necesita separarlas: una se resuelve mostrando el diff al operador, la otra
    es un reintento.

    `estado_actual` viaja en el body para que el cliente pueda mostrar QUÉ
    cambió sin pedir otro GET."""

    def __init__(self, detail: str, estado_actual: list | None = None):
        self.detail = detail
        self.estado_actual = estado_actual or []
        super().__init__(self.detail)


class ConcurrencyConflictError(Exception):
    """Dos requests compitieron por el mismo partido bloqueado con
    `SELECT ... FOR UPDATE` (A1, docs/plans/cierre-pendientes-todos-plan.md)
    y esta transacción no pudo completarse: se agotó `lock_timeout`
    esperando el lock (contención genuina — otro operador está cargando un
    evento en este partido AHORA), o Postgres detectó un deadlock cruzado
    incluso después del reintento único.

    409, con el código estable `evento_conflicto_concurrente` en `detail`
    — nada de header nuevo (`X-Reintentable` se descartó): el interceptor
    global de `client.ts` no tiene visibilidad de mutación por mutación, y
    los ~40 call sites de `MesaPanel.tsx` desestructuran `{data, error}`
    descartando `response`. El frontend discrimina leyendo `error.detail`
    ANTES de traducirlo con `CODIGOS_ERROR_TRADUCIDOS`
    (`frontend/src/api/client.ts`), nunca por substring-match sobre el
    texto en español ya traducido."""

    def __init__(self, detail: str = "evento_conflicto_concurrente"):
        self.detail = detail
        super().__init__(self.detail)


class RateLimitError(Exception):
    """3B-14 (docs/plans/cierre-backlog-todos-plan.md): demasiados intentos
    de login fallidos en la ventana reciente. Distinta de AuthError (401)
    a propósito — un cliente que sepa distinguir "contraseña incorrecta"
    de "bloqueado temporalmente" (429, con Retry-After) no tiene por qué
    tratarlas igual, aunque ninguna pantalla de este proyecto lo haga
    todavía."""

    def __init__(self, detail: str, retry_after_seconds: int):
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds
        super().__init__(self.detail)
