import pandas as pd

def get_recommendation_text(row: dict) -> str:
    name = row.get("name") or row.get("Наименование") or "товар"
    current_stock = row.get("current_stock")
    rec_qty = row.get("recommended_order_qty")
    current_stock = int(current_stock) if pd.notna(current_stock) else 0
    rec_qty = int(rec_qty) if pd.notna(rec_qty) else 0
    order_qty = rec_qty - current_stock

    if order_qty <= 0:
        return (
            f"товар {name} не требует заказа "
            f"(на складе {current_stock}, рекомендуется {rec_qty})"
        )
    return (
        f"нужно заказать товар {name} в таком количестве {order_qty}, "
        f"так как на складе остаток {current_stock}, "
        f"рекомендуемое число {rec_qty}"
    )