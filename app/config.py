"""Configuracion centralizada: lee y valida las variables de entorno."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Conexion a SQL Server ---
    driver: str
    server: str
    database: str
    uid: str
    pwd_sql: str

    # --- Seguridad ---
    api_token: str

    @property
    def connection_string(self) -> str:
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            f"UID={self.uid};"
            f"PWD={self.pwd_sql};"
            "TrustServerCertificate=yes;"
        )


settings = Settings()
