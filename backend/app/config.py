from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "API de Monitoramento de Deslizamentos"
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_database: str = Field(default="deslizamentos_iot", alias="MONGODB_DATABASE")
    mongodb_collection: str = Field(default="leituras", alias="MONGODB_COLLECTION")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
