import json
import os
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.db.models import ImportJob, ImportError
from app.db.session import session_local
from app.services.forecast_service import run_forecast, build_summary
from app.services.stocks_service import run_stocks_processing, add_residue
from app.services.recommendation_service import get_recommendation_text

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


def read_uploaded_file(filepath: str) -> pd.DataFrame:
    ext = Path(filepath).suffix.lower()

    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(filepath)

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

    raise ValueError(f"Не удалось прочитать файл: {last_error}")


def _save_done_payload(job: ImportJob, db, result_df: pd.DataFrame, summary: dict | None = None) -> None:
    records = result_df.to_dict(orient="records")
    payload = {"items": records, "summary": summary or {}}
    job.result_json = json.dumps(payload, ensure_ascii=False)
    job.status = "done"
    db.add(job)
    db.commit()


def _get_latest_done_orders_job(current_job_id: str, db) -> ImportJob | None:
    return (
        db.query(ImportJob)
        .filter(
            ImportJob.kind == "orders",
            ImportJob.status == "done",
            ImportJob.id != current_job_id,
        )
        .order_by(ImportJob.created_at.desc())
        .first()
    )


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
            df = read_uploaded_file(job.filepath)
        except Exception as e:
            add_error(db, job.id, f"Read error: {str(e)}")
            job.status = "failed"
            db.add(job)
            db.commit()
            return

        try:
            summary = {}

            if job.kind == "orders":
                result_df, summary = run_forecast(df)
                _save_done_payload(job, db, result_df, summary)
                return

            if job.kind == "stocks":
                stocks_df = run_stocks_processing(df)

                latest_orders_job = _get_latest_done_orders_job(job.id, db)
                if latest_orders_job is None:
                    add_error(
                        db,
                        job.id,
                        "Сначала загрузите файл orders, чтобы можно было объединить остатки с рекомендациями",
                    )
                    job.status = "failed"
                    db.add(job)
                    db.commit()
                    return

                try:
                    stored_result = json.loads(latest_orders_job.result_json or "{}")
                except json.JSONDecodeError:
                    add_error(db, job.id, "Результат последнего orders-job повреждён")
                    job.status = "failed"
                    db.add(job)
                    db.commit()
                    return

                order_items = stored_result.get("items", [])
                if not order_items:
                    add_error(db, job.id, "В последнем orders-job нет рекомендаций")
                    job.status = "failed"
                    db.add(job)
                    db.commit()
                    return
                recomend_df = pd.DataFrame(order_items)
                merged_df = add_residue(recomend_df, stocks_df)
                merged_df["recommendation_text"] = merged_df.apply(
                    lambda row: get_recommendation_text(row.to_dict()),
                    axis=1
                )
                summary = build_summary(
                    forecast_items=merged_df,
                    cancel_rate_pct=stored_result.get("summary", {}).get("cancel_rate_pct"),
                )
                _save_done_payload(job, db, merged_df, summary)
                return
            result_df = df.copy()
            _save_done_payload(job, db, result_df, summary)
            return

        except Exception as e:
            add_error(db, job.id, f"Processing error: {str(e)}")
            job.status = "failed"
            db.add(job)
            db.commit()
            return

    finally:
        db.close()