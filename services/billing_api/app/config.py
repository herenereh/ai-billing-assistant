from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local-development defaults only. They match docker-compose.yml and are not secrets.
LOCAL_DATABASE_URL = "postgresql+psycopg://billing:billing_local_pw@localhost:5433/billing"
LOCAL_JWT_SECRET = "change-me-local-dev-secret-at-least-32-bytes"


class Settings(BaseSettings):
    """Runtime settings, read from environment variables (or a local .env file).

    APP_ENV=local (default) allows the development defaults above. Any other value
    (Azure sets APP_ENV=production) requires real DATABASE_URL and JWT_SECRET values.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = LOCAL_DATABASE_URL
    jwt_secret: str = LOCAL_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    @model_validator(mode="after")
    def _no_dev_defaults_outside_local(self) -> "Settings":
        if self.app_env == "local":
            return self
        if self.jwt_secret == LOCAL_JWT_SECRET or len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters outside local")
        if self.database_url == LOCAL_DATABASE_URL:
            raise ValueError("DATABASE_URL must be set outside local")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
