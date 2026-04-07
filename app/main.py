from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import engine, Base
from app.api.imports import router as imports_router
from app.api.drafts import router as drafts_router
from app.core.config import settings

app = FastAPI(title="AI for purchasing and inventory management")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Path(settings.STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    Path("./storage").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(imports_router)
app.include_router(drafts_router)