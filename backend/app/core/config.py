"""Configuración de la aplicación, leída de variables de entorno (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    cors_origins: str = "*"
    api_v1_prefix: str = "/api/v1"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
