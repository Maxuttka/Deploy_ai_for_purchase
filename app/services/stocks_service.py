import pandas as pd


def run_stocks_processing(df: pd.DataFrame) -> pd.DataFrame:
    df_ost = df.copy()
    required_cols = ["Артикул", "Свободно", "Розничная цена", "В резерве"]
    missing = [col for col in required_cols if col not in df_ost.columns]
    if missing:
        raise ValueError(f"В файле остатков нет обязательных колонок: {missing}")
    df_ost = df_ost[["Артикул", "Свободно", "Розничная цена", "В резерве"]].copy()
    df_ost["Артикул"] = df_ost["Артикул"].astype(str).str.strip()
    df_ost["Свободно"] = pd.to_numeric(df_ost["Свободно"], errors="coerce").fillna(0)
    df_ost["В резерве"] = pd.to_numeric(df_ost["В резерве"], errors="coerce").fillna(0)
    df_ost["Розничная цена"] = pd.to_numeric(df_ost["Розничная цена"], errors="coerce").fillna(0)
    df_ost = (
        df_ost.groupby("Артикул", as_index=False)
        .agg({
            "Свободно": "sum",
            "Розничная цена": "max",
            "В резерве": "sum",
        })
    )

    return df_ost


def add_residue(recomend_df: pd.DataFrame, df_ost: pd.DataFrame) -> pd.DataFrame:
    df_rec = recomend_df.copy()
    df_rec["Артикул"] = df_rec["article"].astype(str).str.strip()
    df_rec["Наименование"] = df_rec["name"]
    df_rec["Цена закупки"] = df_rec["unit_purchase_price"]
    df_all = df_rec.merge(df_ost, on="Артикул", how="left")
    df_all["Свободно"] = df_all["Свободно"].fillna(0)
    df_all["В резерве"] = df_all["В резерве"].fillna(0)
    df_all["Общий остаток"] = df_all["Свободно"] + df_all["В резерве"]
    df_all["current_stock"] = df_all["Общий остаток"]
    df_all["article"] = df_all["Артикул"]
    df_all["name"] = df_all["Наименование"]
    df_all["unit_purchase_price"] = df_all["Цена закупки"]

    return df_all


def price(df_all: pd.DataFrame) -> pd.DataFrame:
    return df_all[["Наименование", "Цена закупки"]].copy()


def residue(df_all: pd.DataFrame) -> pd.DataFrame:
    return df_all[["Наименование", "Общий остаток"]].copy()