try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field, SecretStr
except ImportError:  # Pydantic v1 compatibility
    from pydantic.v1 import BaseSettings, Field, SecretStr

    SettingsConfigDict = None


class Settings(BaseSettings):
    database_url: str = Field(...)
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    cache_ttl_seconds: int = Field(default=60)
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)
    secret_key: SecretStr = Field(...)
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(
        default=60 * 24,
    )
    model_dir: str = Field(default="models")

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )
    else:

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"


settings = Settings()
