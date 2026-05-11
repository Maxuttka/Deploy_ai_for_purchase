from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./storage/dev.db"
    STORAGE_DIR: str = "./storage/uploads"
    FILE_FORMATS: set[str] = {".csv", ".xlsx"}

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"


settings = Settings()