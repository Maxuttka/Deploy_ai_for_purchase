from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./storage/dev.db"
    STORAGE_DIR: str = "./storage/uploads"
    FILE_FORMATS: set[str] = {".csv"}

settings = Settings()