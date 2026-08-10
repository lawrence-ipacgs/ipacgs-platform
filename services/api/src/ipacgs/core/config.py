"""Application configuration.

Local dev reads from `.env`. In dev/test/prod, DATABASE_URL and other secret
values are Container Apps secretRefs pointing at Key Vault (see
infra/bicep/modules/container-apps.bicep) — this module doesn't fetch from
Key Vault itself except for the one value (the DB connection string) that's
too sensitive to pass as a plain env var even via a Container Apps secret.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    log_level: str = "INFO"

    database_url: str
    key_vault_uri: str = ""

    azure_client_id: str = ""
    azure_tenant_id: str = ""
    entra_api_app_id: str = ""

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    # database_url has no default on purpose (fail fast if it's missing) —
    # pydantic-settings fills it from the environment/`.env` at runtime, which
    # mypy can't see statically.
    return Settings()  # type: ignore[call-arg]
