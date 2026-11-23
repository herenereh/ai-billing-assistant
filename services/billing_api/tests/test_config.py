import pytest
from pydantic import ValidationError

from app.config import LOCAL_JWT_SECRET, Settings

REAL_DB = "postgresql+psycopg://u:p@db.example.postgres.database.azure.com:5432/billing?sslmode=require"
REAL_SECRET = "x" * 48


def test_local_defaults_allowed():
    s = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert s.app_env == "local"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"jwt_secret": LOCAL_JWT_SECRET, "database_url": REAL_DB}, "JWT_SECRET"),
        ({"jwt_secret": "short", "database_url": REAL_DB}, "JWT_SECRET"),
        ({"jwt_secret": REAL_SECRET}, "DATABASE_URL"),
    ],
)
def test_production_rejects_dev_defaults(overrides, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, app_env="production", **overrides)  # pyright: ignore[reportCallIssue]


def test_production_with_real_values():
    s = Settings(_env_file=None, app_env="production", jwt_secret=REAL_SECRET, database_url=REAL_DB)  # pyright: ignore[reportCallIssue]
    assert s.jwt_secret == REAL_SECRET
