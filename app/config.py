"""Centralized configuration: reads and validates the environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQL Server connection
    DRIVER: str
    SERVER: str
    DATABASE: str
    UID: str
    PWD_SQL: str

    # Security
    API_TOKEN: str

    # SharePoint connection
    TENANT_ID: str
    CLIENT_ID: str
    CERT_PATH: str
    CERT_THUMBPRINT: str
    SHAREPOINT_URL: str = "https://intecsaindustrial.sharepoint.com/sites/DesarrolloAutomatizaciones"
    COMMENTS_LIBRARY: str = "Comentarios"

    # Logging (output goes to stdout; systemd/journald handles storage)
    LOG_LEVEL: str = "INFO"


    @property
    def connection_string(self) -> str:
        return (
            f"DRIVER={{{self.DRIVER}}};"
            f"SERVER={self.SERVER};"
            f"DATABASE={self.DATABASE};"
            f"UID={self.UID};"
            f"PWD={self.PWD_SQL};"
            "TrustServerCertificate=yes;"
        )


settings = Settings()
