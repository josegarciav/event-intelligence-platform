from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: str = "development"
    database_url: str
    meetup_api_key: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()

