import json
import os
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.db.models import ImportJob, ImportError
from app.db.session import session_local
from app.services.forecast_service import run_forecast
from app.services.stocks_service import run_stocks_processing

VALID_KINDS = {"stocks", "orders", "collections", "prices"}

def create_job(db, kind: str, filename: str, filepath: str) -> ImportJob:
    job = ImportJob(
        kind=kind,
        filename=filename,
        filepath=filepath,
        status="queued",
        result_json=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def add_error(db, job_id: str, message: str, row_num: int | None = None, field: str | None = None) -> None:
    err = ImportError(job_id=job_id, message=message, row_num=row_num, field=field)
    db.add(err)
    db.commit()

def read_uploaded_csv(filepath: str) -> pd.DataFrame:
    attempts = [
        {"encoding": "utf-8", "sep": ","},
        {"encoding": "utf-8-sig", "sep": ","},
        {"encoding": "utf-16", "sep": "\t"},
        {"encoding": "utf-16le", "sep": "\t"},
        {"encoding": "cp1251", "sep": ";"},
        {"encoding": "cp1251", "sep": ","},
    ]

    last_error = None

    for params in attempts:
        try:
            df = pd.read_csv(filepath, low_memory=False, **params)
            if df.shape[1] >= 3:
                return df
        except Exception as e:
            last_error = e

    raise ValueError(f"Не удалось прочитать CSV: {last_error}")

def process_import_job(job_id: str) -> None:
    db = session_local()
    try:
        job: ImportJob | None = db.get(ImportJob, job_id)
        if job is None:
            return

        job.status = "processing"
        db.add(job)
        db.commit()
        db.refresh(job)

        if job.kind not in VALID_KINDS:
            add_error(db, job.id, f"Unknown kind={job.kind}. Allowed: {VALID_KINDS}")
            job.status = "failed"
            db.add(job)
            db.commit()
            return

        if not os.path.exists(job.filepath):
            add_error(db, job.id, f"File not found on server: {job.filepath}")
            job.status = "failed"
            db.add(job)
            db.commit()
            return

        ext = Path(job.filename).suffix.lower()
        if ext not in settings.FILE_FORMATS:
            add_error(
                db,
                job.id,
                f"Unsupported file extension {ext}. Allowed: {settings.FILE_FORMATS}",
                field="filename",
            )
            job.status = "failed"
            db.add(job)
            db.commit()
            return

        try:
            df = read_uploaded_csv(job.filepath)
        except Exception as e:
            add_error(db, job.id, f"CSV read error: {str(e)}")
            job.status = "failed"
            db.add(job)
            db.commit()
            return

        try:
            summary = {}
            if job.kind == "orders":
                result_df, summary = run_forecast(df)
            elif job.kind == "stocks":
                result_df = run_stocks_processing(df)
            else:
                result_df = df.copy()
        except Exception as e:
            add_error(db, job.id, f"Processing error: {str(e)}")
            job.status = "failed"
            db.add(job)
            db.commit()
            return

        records = result_df.to_dict(orient="records")
        payload = {"items": records, "summary": summary}
        job.result_json = json.dumps(payload, ensure_ascii=False)
        job.status = "done"
        db.add(job)
        db.commit()

    finally:
        db.close()