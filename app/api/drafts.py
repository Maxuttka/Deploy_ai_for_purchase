import json
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Draft
from app.db.session import get_db

router = APIRouter(prefix="/drafts", tags=["drafts"])

class DraftItemIn(BaseModel):
    product_id: str
    name: str
    article: str
    current_stock: int | float = 0
    avg_daily_sales: float = 0
    recommended_order_qty: int = 0
    urgency: str = "low"
    forecast_1m: float | int = 0
    forecast_6m: float | int = 0
    forecast_12m: float | int = 0
    supplier: str | None = None
    price: float | int = 0

class DraftListItem(BaseModel):
    id: int
    supplier: str
    date: str
    items: int
    total: int
    status: str

class DraftAddResponse(BaseModel):
    message: str
    draft_id: int
    items_count: int

class DraftUpdateIn(BaseModel):
    supplier: str | None = None
    items: list[dict] = []

def safe_load_items(items_json: str) -> list[dict]:
    try:
        data = json.loads(items_json)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def normalize_supplier(value: str | None) -> str:
    value = (value or "").strip()
    return value if value else "Не указан"

def calculate_total(items: list[dict]) -> int:
    total = 0
    for item in items:
        qty = item.get("recommended_order_qty") or 0
        price = item.get("price") if item.get("price") is not None else item.get("unit_purchase_price") or 0
        try:
            total += float(qty) * float(price)
        except Exception:
            continue
    return int(total)

def group_items_by_supplier(items: list[dict], fallback_supplier: str = "Не указан") -> dict[str, list[dict]]:
    grouped = defaultdict(list)

    for item in items:
        prepared = dict(item)
        supplier = normalize_supplier(prepared.get("supplier") or fallback_supplier)
        prepared["supplier"] = supplier
        grouped[supplier].append(prepared)

    return dict(grouped)

def build_email_subject(draft: Draft) -> str:
    date_str = draft.created_at.strftime("%d.%m")
    supplier = normalize_supplier(draft.supplier)
    return f"Запрос Линуксцентр {date_str} {supplier}"

def build_email_positions(items: list[dict]) -> str:
    lines = []
    for item in items:
        qty = item.get("recommended_order_qty") or 0
        article = item.get("article") or "-"
        name = item.get("name") or "Без названия"
        lines.append(f"- {qty} шт. | {article} | {name}")
    return "\n".join(lines)

def build_email_body(draft: Draft, items: list[dict]) -> str:
    positions_text = build_email_positions(items)

    return (
        "Добрый день.\n\n"
        "Выставите, пожалуйста, счёт:\n"
        f"{positions_text}\n\n"
        "с доставкой:\n"
        "<наш адрес или адрес ПВЗ СДЭК>\n"
        "или:\n"
        "заберём сами <адрес продавца/офиса/склада в Петербурге>\n\n"
        "Наши реквизиты во вложении.\n\n"
        "С уважением\n"
        "<Фамилия Имя>\n\n"
        "linuxcenter.shop\n"
        "+7(812)309-06-86\n"
        "+7(499)28-38-606"
    )

@router.get("/", response_model=list[DraftListItem])
def list_drafts(db: Session = Depends(get_db)):
    drafts = db.query(Draft).order_by(Draft.created_at.desc(), Draft.id.desc()).all()

    result = []
    for draft in drafts:
        items = safe_load_items(draft.items_json)
        result.append(
            DraftListItem(
                id=draft.id,
                supplier=draft.supplier,
                date=draft.created_at.strftime("%d.%m.%Y"),
                items=len(items),
                total=draft.total_amount,
                status=draft.status,
            )
        )

    return result

@router.post("/items", response_model=DraftAddResponse)
def add_item_to_draft(item: DraftItemIn, db: Session = Depends(get_db)):
    draft = (
        db.query(Draft)
        .filter(Draft.status == "draft", Draft.parent_draft_id.is_(None))
        .order_by(Draft.created_at.desc())
        .first()
    )

    if draft is None:
        draft = Draft(
            supplier="Не указан",
            status="draft",
            total_amount=0,
            items_json="[]",
            parent_draft_id=None,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

    items = safe_load_items(draft.items_json)

    existing = next((x for x in items if x.get("article") == item.article), None)

    if existing:
        existing["recommended_order_qty"] = int(existing.get("recommended_order_qty", 0)) + int(item.recommended_order_qty or 0)
        existing["forecast_1m"] = float(existing.get("forecast_1m", 0)) + float(item.forecast_1m or 0)
        existing["forecast_6m"] = float(existing.get("forecast_6m", 0)) + float(item.forecast_6m or 0)
        existing["forecast_12m"] = float(existing.get("forecast_12m", 0)) + float(item.forecast_12m or 0)

        if not existing.get("supplier") and item.supplier:
            existing["supplier"] = item.supplier
    else:
        payload = item.model_dump()
        payload["supplier"] = normalize_supplier(payload.get("supplier"))
        items.append(payload)

    draft.items_json = json.dumps(items, ensure_ascii=False)
    draft.total_amount = calculate_total(items)
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return DraftAddResponse(
        message="Товар добавлен в черновик",
        draft_id=draft.id,
        items_count=len(items),
    )

@router.get("/{draft_id}")
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Черновик не найден")

    items = safe_load_items(draft.items_json)
    normalized_items = []
    for item in items:
        normalized = dict(item)
        if normalized.get("price") is None:
            normalized["price"] = normalized.get("unit_purchase_price") or 0
        normalized_items.append(normalized)

    return {
        "id": draft.id,
        "supplier": draft.supplier,
        "status": draft.status,
        "total_amount": draft.total_amount,
        "created_at": draft.created_at.strftime("%d.%m.%Y"),
        "items": normalized_items,
        "parent_draft_id": draft.parent_draft_id,
    }

@router.put("/{draft_id}")
def update_draft(draft_id: int, data: DraftUpdateIn, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Черновик не найден")

    root_draft = draft
    if draft.parent_draft_id is not None:
        parent = db.query(Draft).filter(Draft.id == draft.parent_draft_id).first()
        if parent:
            root_draft = parent

    items = data.items or []
    fallback_supplier = normalize_supplier(data.supplier or root_draft.supplier)
    grouped = group_items_by_supplier(items, fallback_supplier=fallback_supplier)
    child_drafts = db.query(Draft).filter(Draft.parent_draft_id == root_draft.id).all()
    for child in child_drafts:
        db.delete(child)
    db.flush()

    if not grouped:
        root_draft.supplier = fallback_supplier
        root_draft.items_json = "[]"
        root_draft.total_amount = 0
        db.add(root_draft)
        db.commit()
        db.refresh(root_draft)
        return {
            "message": "Черновик сохранён",
            "draft_id": root_draft.id,
            "total_amount": root_draft.total_amount,
            "created_ids": [root_draft.id],
        }

    ordered_groups = sorted(
        grouped.items(),
        key=lambda x: (x[0] == "Не указан", x[0])
    )

    first_supplier, first_items = ordered_groups[0]

    root_draft.supplier = first_supplier
    root_draft.items_json = json.dumps(first_items, ensure_ascii=False)
    root_draft.total_amount = calculate_total(first_items)
    root_draft.parent_draft_id = None
    db.add(root_draft)

    created_ids = [root_draft.id]

    for supplier, supplier_items in ordered_groups[1:]:
        new_draft = Draft(
            supplier=supplier,
            status="draft",
            total_amount=calculate_total(supplier_items),
            items_json=json.dumps(supplier_items, ensure_ascii=False),
            parent_draft_id=root_draft.id,
        )
        db.add(new_draft)
        db.flush()
        created_ids.append(new_draft.id)

    db.commit()
    db.refresh(root_draft)

    if len(ordered_groups) == 1:
        message = "Черновик сохранён"
    else:
        message = f"Черновик разделён по поставщикам. Создано черновиков: {len(created_ids)}"

    return {
        "message": message,
        "draft_id": root_draft.id,
        "total_amount": root_draft.total_amount,
        "created_ids": created_ids,
    }

@router.delete("/{draft_id}")
def delete_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Черновик не найден")
    if draft.parent_draft_id is None:
        children = db.query(Draft).filter(Draft.parent_draft_id == draft.id).all()
        for child in children:
            db.delete(child)

    db.delete(draft)
    db.commit()

    return {"message": "Черновик удалён"}

@router.get("/{draft_id}/email-template")
def get_draft_email_template(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Черновик не найден")

    supplier = normalize_supplier(draft.supplier)
    if supplier == "Не указан":
        raise HTTPException(status_code=400, detail="У черновика не выбран поставщик")

    items = safe_load_items(draft.items_json)
    if not items:
        raise HTTPException(status_code=400, detail="В черновике нет товаров")

    subject = build_email_subject(draft)
    body = build_email_body(draft, items)

    full_text = f"Тема: {subject}\n\n{body}"

    return {
        "draft_id": draft.id,
        "supplier": supplier,
        "subject": subject,
        "body": body,
        "full_text": full_text,
    }