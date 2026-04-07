import uuid
from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.db.session import Base

class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(36), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    filepath: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(36), nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    errors: Mapped[list["ImportError"]] = relationship(
        "ImportError",
        back_populates="job",
        cascade="all, delete-orphan"
    )

class ImportError(Base):
    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("import_jobs.id"), nullable=False)
    row_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped["ImportJob"] = relationship("ImportJob", back_populates="errors")

class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier: Mapped[str] = mapped_column(String(255), default="Не указан", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    parent_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("drafts.id"),
        nullable=True
    )