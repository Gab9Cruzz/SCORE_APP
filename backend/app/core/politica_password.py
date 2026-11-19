"""Política de contraseñas (TASK-033, SEC-03).

Un mínimo de largo y una lista corta de contraseñas que aparecen primero en
cualquier diccionario de ataque. No pretende ser exhaustiva: el rate limit
del login (UsuarioService.login) es el que frena la fuerza bruta; esto solo
evita que alguien elija exactamente lo que se prueba primero.

Se aplica a contraseñas NUEVAS (alta, edición, cambio propio). La del
administrador inicial se valida aparte, al arrancar en producción
(config.py, _ADMIN_PASSWORD_LARGO_MINIMO).
"""

LARGO_MINIMO = 10

_COMUNES = frozenset(
    {
        "0123456789",
        "1234567890",
        "0987654321",
        "1111111111",
        "12345678910",
        "1q2w3e4r5t",
        "abcdefghij",
        "abc1234567",
        "qwertyuiop",
        "asdfghjkl1",
        "password12",
        "password123",
        "contrasena",
        "contraseña",
        "contrasena1",
        "contraseña1",
        "contrasena123",
        "contraseña123",
        "administrador",
        "admin12345",
        "admin123456",
        "iloveyou12",
        "ecuador123",
        "guayaquil1",
        "barcelona1",
        "futbol1234",
    }
)


def validar_password_nueva(valor: str) -> str:
    """Devuelve el valor tal cual o lanza ValueError con el motivo (Pydantic
    lo convierte en un 422 con ese mensaje)."""
    if len(valor) < LARGO_MINIMO:
        raise ValueError(f"La contraseña debe tener al menos {LARGO_MINIMO} caracteres.")
    if valor.strip().lower() in _COMUNES:
        raise ValueError("Esa contraseña es demasiado común. Elegí otra.")
    return valor
