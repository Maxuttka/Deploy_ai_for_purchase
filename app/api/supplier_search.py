from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.gemini_supplier_search import search_suppliers_with_gemini


router = APIRouter(prefix="/supplier-search", tags=["supplier-search"])


class SupplierSearchRequest(BaseModel):
    query: str


class SupplierSearchResponse(BaseModel):
    query: str
    items: list[dict]


@router.post("/", response_model=SupplierSearchResponse)
def supplier_search(data: SupplierSearchRequest):
    query = data.query.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Пустой поисковый запрос")

    try:
        items = search_suppliers_with_gemini(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return SupplierSearchResponse(
        query=query,
        items=items,
    )