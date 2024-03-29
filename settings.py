from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    path: str = Field("/webhook/country-ded", alias="URL_PATH")
    port: int = Field(3010)
    host: str = Field("localhost")

    mongodb_url: str = Field(..., alias="MONGODB_URL")


settings = Settings()
