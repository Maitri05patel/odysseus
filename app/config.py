from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "sqlite:///./odysseus.db"
    QUOTE_TTL_MINUTES: int = 15
    DEBUG: bool = False


settings = Settings()
