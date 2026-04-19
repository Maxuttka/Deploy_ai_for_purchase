import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ImportJob, ImportError
from app.db.session import get_db
from app.services.import_service import create_job, process_import_job, VALID_KINDS

router = APIRouter(prefix="/imports")


class JobResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    filename: str


class ErrorItem(BaseModel):
    row_num: int | None
    field: str | None
    message: str


class ForecastResponse(BaseModel):
    job_id: str
    status: str
    items: list[dict]
    summary: dict = Field(default_factory=dict)


class ImportListItem(BaseModel):
    job_id: str
    kind: str
    status: str
    filename: str
    created_at: datetime


@router.post("/{kind}", response_model=JobResponse)
def upload_import(
    kind: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown kind={kind}. Allowed: {VALID_KINDS}")

    temp_path = str(Path(settings.STORAGE_DIR) / "tmp" / file.filename)
    job = create_job(db=db, kind=kind, filename=file.filename, filepath=temp_path)

    job_dir = Path(settings.STORAGE_DIR) / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    final_path = job_dir / file.filename

    with final_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job.filepath = str(final_path)
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_import_job, job.id)

    return JobResponse(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        filename=job.filename,
    )


@router.get("", response_model=list[ImportListItem])
def list_imports(db: Session = Depends(get_db)):
    jobs = db.query(ImportJob).order_by(ImportJob.created_at.desc()).all()
    return [
        ImportListItem(
            job_id=job.id,
            kind=job.kind,
            status=job.status,
            filename=job.filename,
            created_at=job.created_at,
        )
        for job in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job: ImportJob | None = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        filename=job.filename,
    )


@router.get("/{job_id}/errors", response_model=list[ErrorItem])
def get_job_errors(job_id: str, db: Session = Depends(get_db)):
    job: ImportJob | None = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    errs = db.query(ImportError).filter(ImportError.job_id == job_id).order_by(ImportError.id.asc()).all()
    return [ErrorItem(row_num=e.row_num, field=e.field, message=e.message) for e in errs]


@router.get("/{job_id}/result", response_model=ForecastResponse)
def get_job_result(job_id: str, db: Session = Depends(get_db)):
    job: ImportJob | None = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "done":
        raise HTTPException(status_code=409, detail=f"Job is not completed yet. Current status: {job.status}")

    if not job.result_json:
        return ForecastResponse(job_id=job.id, status=job.status, items=[], summary={})

    try:
        stored_result = json.loads(job.result_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Stored result is corrupted")

    if isinstance(stored_result, list):
        items = stored_result
        summary = {}
    elif isinstance(stored_result, dict):
        items = stored_result.get("items", [])
        summary = stored_result.get("summary", {}) or {}
    else:
        raise HTTPException(status_code=500, detail="Stored result has unsupported format")

    return ForecastResponse(
        job_id=job.id,
        status=job.status,
        items=items,
        summary=summary,
    )