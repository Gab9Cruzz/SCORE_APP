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


def create_access_token(subject: str, rol: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "rol": rol, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
