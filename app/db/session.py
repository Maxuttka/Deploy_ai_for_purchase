from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.DATABASE_URL, echo=False, future=True)
session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()