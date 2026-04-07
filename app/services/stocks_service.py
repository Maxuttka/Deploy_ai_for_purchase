import pandas as pd

def run_stocks_processing(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = [
        "Наименование",
        "ID товара",
        "Цена",
        "Кол-во",
        "Свободно",
        "В резерве",
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"В файле остатков нет обязательных колонок: {missing}")
    work = df.copy()
    work["ID товара"] = work["ID товара"].astype(str)
    work["Наименование"] = work["Наименование"].fillna("Без названия")
    for col in ["Цена", "Кол-во", "Свободно", "В резерве"]:
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)
    result = work[[
        "ID товара",
        "Наименование",
        "Цена",
        "Кол-во",
        "Свободно",
        "В резерве",
    ]].copy()
    result = result.rename(columns={
        "ID товара": "product_id",
        "Наименование": "name",
        "Цена": "price",
        "Кол-во": "current_stock",
        "Свободно": "available_stock",
        "В резерве": "reserved_stock",
    })
    return result.sort_values("name").reset_index(drop=True)