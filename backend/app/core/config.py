"""Configuración de la aplicación, leída de variables de entorno (.env)."""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores que aparecen en el repositorio (defaults, .env.example, compose):
# son públicos, así que en producción equivalen a no tener secreto.
_JWT_DE_EJEMPLO = {"change-me-please-do-not-use-in-production"}
_ADMIN_PASSWORD_DE_EJEMPLO = {"admin1234", "change-me-please"}
_JWT_LARGO_MINIMO = 32
_ADMIN_PASSWORD_LARGO_MINIMO = 12


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # TASK-005 (SEC-02, OPS-04): en "produccion" la app se niega a arrancar
    # con secretos de ejemplo (ver _exigir_secretos_propios_en_produccion).
    # "desarrollo" no valida nada, como hasta ahora.
    entorno: Literal["desarrollo", "produccion"] = "desarrollo"

    database_url: str
    test_database_url: str | None = None

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    # Bootstrap del primer Admin: si la tabla usuarios está vacía al arrancar,
    # la API crea esta cuenta sola (ver app/main.py). No hay seed de usuarios
    # en /database porque las contraseñas no se versionan en SQL.
    admin_username: str = "admin"
    admin_password: str = "admin1234"
    admin_nombre: str = "Administrador"

    # Retención de la bitácora de accesos (tabla ACCESOS). Un mes por
    # defecto: es una bitácora operativa para detectar intentos raros, no un
    # archivo histórico, y sin purga crece sin techo. La purga corre al
    # arrancar la API (ver app/main.py). 0 = no purgar nunca.
    accesos_retencion_dias: int = 30

    # Retención de la auditoría de cambios (tabla AUDITORIA: alta/
    # modificación/baja de cualquier entidad). Un mes por defecto, mismo
    # criterio y mismo mecanismo de purga que accesos_retencion_dias (ver
    # app/main.py). 0 = no purgar nunca.
    auditoria_retencion_dias: int = 30

    # Rate limiting de login (3B-14, docs/plans/cierre-backlog-todos-plan.md):
    # 5 fallos de CREDENCIALES (no cuenta 'inactivo' ni 'bloqueado', ver
    # UsuarioService.login) por (username, IP) en los últimos 15 minutos
    # bloquea nuevos intentos por otros 15 minutos. 0 en cualquiera de los
    # dos apaga el rate limiting por completo (mismo criterio "0 = off"
    # que accesos_retencion_dias).
    login_rate_limit_intentos: int = 5
    login_rate_limit_ventana_minutos: int = 15
    # TASK-004 (SEC-01): tope por cuenta, sin importar la IP, en la misma
    # ventana. Más alto que el de (usuario, IP) para que nadie pueda
    # bloquear una cuenta ajena con unos pocos intentos, pero frena un
    # ataque repartido entre muchas IPs. 0 lo apaga.
    login_rate_limit_intentos_cuenta: int = 20

    # TASK-004 (SEC-01): IPs de los proxies cuyo X-Forwarded-For se acepta,
    # separadas por coma. Vacío (default) = la app está expuesta directo y
    # la cabecera se ignora: la puede inventar cualquiera.
    trusted_proxies: str = ""

    cors_origins: str = "*"
    api_v1_prefix: str = "/api/v1"

    # A1 (docs/plans/cierre-pendientes-todos-plan.md) — concurrencia en el
    # camino en vivo de eventos-partido. `evento_lock_timeout_ms`: cuánto
    # espera el `SELECT ... FOR UPDATE` del partido antes de rendirse con
    # 409 (Postgres por default espera para siempre, 0). `evento_lock_log_
    # umbral_ms`: a partir de qué espera (haya terminado en éxito o en
    # timeout) se loguea como posible contención — separado del timeout
    # real para poder ver el problema venir antes de que empiece a fallar.
    # `evento_concurrencia_reintentos`: reintentos de un deadlock cruzado
    # (40P01) antes de rendirse con 409 — nunca de una contención genuina,
    # que ya esperó lo que había que esperar.
    evento_lock_timeout_ms: int = 3000
    evento_lock_log_umbral_ms: int = 500
    evento_concurrencia_reintentos: int = 1

    @model_validator(mode="after")
    def _exigir_secretos_propios_en_produccion(self) -> "Settings":
        """Junta todos los problemas en un solo error para que quien
        despliega los corrija de una vez, cada uno con el nombre de la
        variable de entorno que lo arregla."""
        if self.entorno != "produccion":
            return self
        problemas: list[str] = []
        if self.jwt_secret_key in _JWT_DE_EJEMPLO or len(self.jwt_secret_key) < _JWT_LARGO_MINIMO:
            problemas.append(
                f"JWT_SECRET_KEY: usá un valor propio de {_JWT_LARGO_MINIMO} caracteres o más "
                '(python -c "import secrets; print(secrets.token_hex(32))").'
            )
        if (
            self.admin_password in _ADMIN_PASSWORD_DE_EJEMPLO
            or len(self.admin_password) < _ADMIN_PASSWORD_LARGO_MINIMO
        ):
            problemas.append(
                f"ADMIN_PASSWORD: no puede ser un valor de ejemplo y necesita "
                f"{_ADMIN_PASSWORD_LARGO_MINIMO} caracteres o más."
            )
        if self.cors_origins.strip() == "*":
            problemas.append("CORS_ORIGINS: listá los orígenes del frontend en vez de '*'.")
        if problemas:
            raise ValueError("Configuración insegura para ENTORNO=produccion. " + " ".join(problemas))
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_proxies_list(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
