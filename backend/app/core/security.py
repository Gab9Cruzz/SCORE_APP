"""Hash de contraseñas y JWT.

Usa la librería `bcrypt` directamente en vez de passlib: passlib está sin
mantenimiento y su self-test interno rompe con bcrypt>=4.1 (bcrypt dejó de
truncar en silencio a los 72 bytes y ahora lanza ValueError, que es
justamente lo que ese self-test dispara). Nada de esto es visible desde
afuera: hash_password/verify_password son la misma interfaz.

Password_Hash en la tabla usuarios exige >= 20 caracteres (ver
02_constraints.sql): un hash bcrypt entra sobrado (60 chars).
"""
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.reloj import zona_negocio

settings = get_settings()

# bcrypt ignora todo lo que pase de 72 bytes; truncar acá a propósito para
# que dos contraseñas que sólo difieren después del byte 72 no se traten
# como iguales por accidente, y para que un password larguísimo no rompa
# con ValueError en vez de fallar limpio en la validación de Pydantic.
_MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    try:
        return bcrypt.checkpw(pw_bytes, password_hash.encode("utf-8"))
    except ValueError:
        # Hash corrupto/con formato inesperado: tratar como no coincide, no
        # como 500.
        return False


def create_access_token(subject: str, rol: str, emitido_ms_minimo: int | None = None) -> str:
    """`emitido_ms_minimo` (TASK-033): el token nuevo del cambio de
    contraseña tiene que quedar DESPUÉS de la marca que invalida los
    anteriores, aunque el reloj no haya avanzado (ver token_revocado)."""
    ahora = datetime.now(UTC)
    expire = ahora + timedelta(minutes=settings.jwt_expire_minutes)
    emitido_ms = int(ahora.timestamp() * 1000)
    if emitido_ms_minimo is not None:
        emitido_ms = max(emitido_ms, emitido_ms_minimo)
    # `iat` e `iat_ms` (TASK-033): permiten rechazar los tokens emitidos antes
    # de que la cuenta invalidara sus sesiones (ver token_revocado).
    # python-jose exige `iat` entero, en segundos; con eso solo, un login y un
    # cambio de contraseña en el mismo segundo serían indistinguibles, por eso
    # va también en milisegundos.
    payload: dict[str, Any] = {
        "sub": subject,
        "rol": rol,
        "exp": expire,
        "iat": int(ahora.timestamp()),
        "iat_ms": emitido_ms,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def marca_en_ms(tokens_validos_desde: datetime) -> int:
    """USUARIOS.Tokens_Validos_Desde (TIMESTAMP sin zona, hora del negocio)
    en milisegundos desde epoch, para comparar con `iat_ms`."""
    return int(tokens_validos_desde.replace(tzinfo=zona_negocio()).timestamp() * 1000)


def token_revocado(payload: dict[str, Any], tokens_validos_desde: datetime | None) -> bool:
    """True si el token se emitió en o antes del momento en que la cuenta
    invalidó sus sesiones (TASK-033: cambio de contraseña o desactivación).

    "En o antes" (`<=`), no "antes": el reloj del sistema avanza a saltos
    (unos 15 ms en Windows), así que un login y una baja hechos uno detrás
    del otro pueden dar el MISMO milisegundo. Con `<` ese token viejo
    sobrevivía. El token nuevo del cambio de contraseña se emite con
    `emitido_ms_minimo = marca + 1` para no caer en la misma trampa.

    Un token sin `iat` es anterior a TASK-033: si la cuenta ya invalidó
    sesiones alguna vez, no sirve."""
    if tokens_validos_desde is None:
        return False
    emitido_ms = payload.get("iat_ms")
    if not isinstance(emitido_ms, int):
        iat = payload.get("iat")
        if not isinstance(iat, int):
            return True
        emitido_ms = iat * 1000
    return emitido_ms <= marca_en_ms(tokens_validos_desde)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
