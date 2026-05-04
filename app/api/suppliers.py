from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Supplier
from app.db.session import get_db

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierCreate(BaseModel):
    brand: str
    category: str
    city: str
    legal_entity: str
    shipping_method: str = "-"
    website: str = "-"
    contact: str
    phone: str = "-"
    email: str = "-"
    status: str = "актив"
    buyer: str = "-"
    work_conditions: str = "-"


class SupplierOut(BaseModel):
    id: int
    brand: str
    category: str
    city: str
    legal_entity: str
    shipping_method: str
    website: str
    manager_name: str
    contact_info: str
    phone: str
    email: str
    status: str
    buyer: str
    work_conditions: str

    class Config:
        from_attributes = True

def clean_supplier_text(value: str | None) -> str:
    value = (value or "").strip()

    bad_values = {
        "",
        "-",
        "nan",
        "none",
        "#error!",
        "#n/a",
        "#value!",
        "#ref!",
        "#div/0!",
        "#name?",
        "#null!",
    }

    if value.lower() in bad_values:
        return "-"

    return value

def build_contact_info(phone: str | None, email: str | None) -> str:
    parts = []


    phone = clean_supplier_text(phone)
    email = clean_supplier_text(email)
    if phone != "-":
        parts.append(phone)
    if email != "-":
        parts.append(email)

    return ", ".join(parts) if parts else "-"


@router.get("/", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).order_by(Supplier.id.asc()).all()

    result = []
    for s in suppliers:
        result.append(
            SupplierOut(
                id=s.id,
                brand=s.brand,
                category=s.category,
                city=s.city,
                legal_entity=s.legal_entity,
                shipping_method=s.shipping_method,
                website=s.website,
                manager_name=s.contact,
                contact_info=build_contact_info(s.phone, s.email),
                phone=s.phone,
                email=s.email,
                status=s.status,
                buyer=s.buyer,
                work_conditions=s.work_conditions,
            )
        )

    return result

@router.post("/", response_model=SupplierOut)
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db)):
    supplier = Supplier(
        brand=data.brand.strip(),
        category=data.category.strip(),
        city=data.city.strip(),
        legal_entity=data.legal_entity.strip(),
        shipping_method=(data.shipping_method or "-").strip(),
        website=(data.website or "-").strip(),
        contact=data.contact.strip(),
        phone=(data.phone or "-").strip(),
        email=(data.email or "-").strip(),
        status=(data.status or "актив").strip(),
        buyer=(data.buyer or "-").strip(),
        work_conditions=(data.work_conditions or "-").strip(),
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")

    db.delete(supplier)
    db.commit()
    return {"message": "Поставщик удалён"}