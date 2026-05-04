import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from app.services.recommendation_service import get_recommendation_text


PROJECT_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_DIR / "models"
FALLBACK_MODELS_DIR = PROJECT_DIR


def prepare_monthly_demand(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    data["Дата создания"] = pd.to_datetime(data["Дата создания"], errors="coerce", dayfirst=True)
    data["Кол-во"] = pd.to_numeric(data["Кол-во"], errors="coerce")

    data = data.dropna(subset=["ID товара", "Дата создания", "Кол-во"])
    data["ID товара"] = data["ID товара"].astype(str)

    data["month"] = data["Дата создания"].dt.to_period("M").dt.to_timestamp()

    monthly = (
        data.groupby(["ID товара", "month"], as_index=False)["Кол-во"]
        .sum()
        .rename(columns={"Кол-во": "demand"})
    )

    return monthly


def expand_full_month_grid(monthly: pd.DataFrame) -> pd.DataFrame:
    all_ids = monthly["ID товара"].unique()

    min_month = monthly["month"].min()
    max_month = monthly["month"].max()

    all_months = pd.date_range(min_month, max_month, freq="MS")

    full_index = pd.MultiIndex.from_product(
        [all_ids, all_months],
        names=["ID товара", "month"]
    )

    full_df = (
        monthly.set_index(["ID товара", "month"])
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    return full_df


def add_time_features(full_df: pd.DataFrame) -> pd.DataFrame:
    df_feat = full_df.copy()
    df_feat = df_feat.sort_values(["ID товара", "month"]).reset_index(drop=True)

    g = df_feat.groupby("ID товара")

    for lag in [1, 2, 3, 6, 12]:
        df_feat[f"lag_{lag}"] = g["demand"].shift(lag)

    for window in [1, 3, 6, 12]:
        df_feat[f"roll_sum_{window}"] = (
            g["demand"].shift(1).rolling(window=window, min_periods=1).sum()
        )

    for window in [3, 6, 12]:
        df_feat[f"roll_mean_{window}"] = (
            g["demand"].shift(1).rolling(window=window, min_periods=1).mean()
        )

    for window in [3, 6, 12]:
        df_feat[f"roll_std_{window}"] = (
            g["demand"].shift(1).rolling(window=window, min_periods=1).std()
        )

    for window in [3, 6, 12]:
        df_feat[f"roll_max_{window}"] = (
            g["demand"].shift(1).rolling(window=window, min_periods=1).max()
        )
        df_feat[f"roll_min_{window}"] = (
            g["demand"].shift(1).rolling(window=window, min_periods=1).min()
        )

    df_feat["trend_3_vs_prev3"] = (
        df_feat["roll_mean_3"] -
        g["demand"].shift(4).rolling(window=3, min_periods=1).mean()
    )

    df_feat["trend_6_vs_prev6"] = (
        df_feat["roll_mean_6"] -
        g["demand"].shift(7).rolling(window=6, min_periods=1).mean()
    )

    df_feat["month_num"] = df_feat["month"].dt.month
    df_feat["month_sin"] = np.sin(2 * np.pi * df_feat["month_num"] / 12)
    df_feat["month_cos"] = np.cos(2 * np.pi * df_feat["month_num"] / 12)

    df_feat["series_age"] = g.cumcount()

    return df_feat


def add_targets(df_feat: pd.DataFrame) -> pd.DataFrame:
    df_target = df_feat.copy()
    g = df_target.groupby("ID товара")

    df_target["target_1m"] = g["demand"].shift(-1)

    df_target["target_6m"] = (
        g["demand"]
        .transform(lambda s: s.shift(-1).rolling(window=6, min_periods=6).sum())
    )

    df_target["target_12m"] = (
        g["demand"]
        .transform(lambda s: s.shift(-1).rolling(window=12, min_periods=12).sum())
    )

    return df_target


def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    monthly = prepare_monthly_demand(df)
    full_df = expand_full_month_grid(monthly)
    feat_df = add_time_features(full_df)
    feat_df = add_targets(feat_df)
    return feat_df


def get_feature_columns() -> list[str]:
    return [
        "ID товара",
        "lag_1", "lag_2", "lag_3", "lag_6", "lag_12",
        "roll_sum_1", "roll_sum_3", "roll_sum_6", "roll_sum_12",
        "roll_mean_3", "roll_mean_6", "roll_mean_12",
        "roll_std_3", "roll_std_6", "roll_std_12",
        "roll_max_3", "roll_max_6", "roll_max_12",
        "roll_min_3", "roll_min_6", "roll_min_12",
        "trend_3_vs_prev3", "trend_6_vs_prev6",
        "month_num", "month_sin", "month_cos",
        "series_age",
    ]


def make_model(feature_cols: list[str]) -> Pipeline:
    categorical_features = ["ID товара"]
    numeric_features = [col for col in feature_cols if col not in categorical_features]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("ohe", OneHotEncoder(handle_unknown="ignore")),
                ]),
                categorical_features,
            ),
            (
                "num",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
                    ("scaler", StandardScaler()),
                ]),
                numeric_features,
            ),
        ]
    )

    return Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", LinearRegression()),
    ])


def train_models(df: pd.DataFrame) -> dict:
    feat_df = build_feature_table(df)
    feature_cols = get_feature_columns()

    models = {}
    targets = {
        "1m": "target_1m",
        "6m": "target_6m",
        "12m": "target_12m",
    }

    for horizon_name, target_col in targets.items():
        work = feat_df.dropna(subset=[target_col]).copy()
        if work.empty:
            raise ValueError(f"Not enough data to train model {horizon_name}")

        X_train = work[feature_cols]
        y_train = work[target_col]

        model = make_model(feature_cols)
        model.fit(X_train, y_train)
        models[horizon_name] = model

    return models


def load_models() -> dict:
    model_filenames = {
        "1m": "1m_model.pkl",
        "6m": "6m_model.pkl",
        "12m": "12m_model.pkl",
    }

    models = {}
    for horizon, filename in model_filenames.items():
        preferred_path = MODELS_DIR / filename
        fallback_path = FALLBACK_MODELS_DIR / filename
        model_path = preferred_path if preferred_path.exists() else fallback_path
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {preferred_path} or {fallback_path}")
        models[horizon] = joblib.load(model_path)

    return models


def predict_future_demand(df: pd.DataFrame, models: dict) -> pd.DataFrame:
    feat_df = build_feature_table(df)
    feature_cols = get_feature_columns()
    forecast_month = feat_df["month"].max()
    forecast_df = feat_df[feat_df["month"] == forecast_month].copy()

    if forecast_df.empty:
        raise ValueError("Не удалось подготовить данные для прогноза")

    X_forecast = forecast_df[feature_cols].copy()
    X_forecast["ID товара"] = X_forecast["ID товара"].astype(str)

    pred_1m = models["1m"].predict(X_forecast)
    pred_6m = models["6m"].predict(X_forecast)
    pred_12m = models["12m"].predict(X_forecast)

    result = pd.DataFrame({
        "ID товара": forecast_df["ID товара"].astype(str).values,
        "ожидаемый спрос в следующем месяце": np.maximum(pred_1m, 0),
        "ожидаемый спрос в следующем полугодии": np.maximum(pred_6m, 0),
        "ожидаемый спрос в следующем году": np.maximum(pred_12m, 0),
    })

    return result.sort_values("ID товара").reset_index(drop=True)


def _build_product_info(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["ID товара"] = data["ID товара"].astype(str)
    data["_row_order"] = np.arange(len(data))
    data["_sort_date"] = pd.to_datetime(data["Дата создания"], errors="coerce", dayfirst=True)

    if "Цена закупки" not in data.columns:
        data["Цена закупки"] = np.nan
    if "Цена" not in data.columns:
        data["Цена"] = np.nan
    if "Артикул" not in data.columns:
        data["Артикул"] = data["ID товара"]
    if "Наименование" not in data.columns:
        data["Наименование"] = "Товар " + data["ID товара"]

    data["Цена закупки"] = pd.to_numeric(data["Цена закупки"], errors="coerce")
    data["Цена"] = pd.to_numeric(data["Цена"], errors="coerce")

    product_info = (
        data[["ID товара", "Наименование", "Артикул", "Цена закупки", "Цена", "_sort_date", "_row_order"]]
        .dropna(subset=["ID товара"])
        .sort_values(["_sort_date", "_row_order"])
        .drop_duplicates(subset=["ID товара"], keep="last")
        .copy()
    )

    product_info["Артикул"] = product_info["Артикул"].astype(str).str.strip()

    product_info["unit_purchase_price"] = (
        product_info["Цена закупки"]
        .fillna(product_info["Цена"])
        .fillna(0)
        .round(2)
    )

    return product_info[["ID товара", "Наименование", "Артикул", "unit_purchase_price"]]


def _calculate_cancel_rate(df: pd.DataFrame) -> float | None:
    if "Статус" not in df.columns:
        return None

    statuses = df["Статус"].fillna("").astype(str).str.strip()
    valid_statuses = statuses[statuses != ""]
    if valid_statuses.empty:
        return None

    cancelled = valid_statuses.str.lower().str.startswith("отмен")
    return round(float(cancelled.mean() * 100), 2)


def build_summary(forecast_items: pd.DataFrame, cancel_rate_pct: float | None = None) -> dict[str, float | int | None]:
    total_items = int(len(forecast_items))
    items_to_order_count = int((forecast_items["recommended_order_qty"] > 0).sum())
    urgent_items_count = int((forecast_items["urgency"] == "high").sum())

    budget_to_procure = round(
        float((forecast_items["recommended_order_qty"] * forecast_items["unit_purchase_price"]).sum()),
        2,
    )

    total_current_stock = round(float(forecast_items["current_stock"].fillna(0).sum()), 2)

    return {
        "items_total_count": total_items,
        "items_to_order_count": items_to_order_count,
        "urgent_items_count": urgent_items_count,
        "budget_to_procure": budget_to_procure,
        "total_current_stock": total_current_stock,
        "cancel_rate_pct": cancel_rate_pct,
    }


def run_forecast(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int | None]]:
    required_cols = ["ID товара", "Дата создания", "Кол-во"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"В CSV нет обязательных колонок: {missing}")

    try:
        models = load_models()
    except Exception:
        models = train_models(df.copy())

    result = predict_future_demand(df.copy(), models)
    product_info = _build_product_info(df)

    product_info["ID товара"] = product_info["ID товара"].astype(str)
    result["ID товара"] = result["ID товара"].astype(str)

    merged = result.merge(product_info, on="ID товара", how="left")

    merged["product_id"] = merged["ID товара"]
    merged["name"] = merged["Наименование"].fillna("Товар " + merged["ID товара"])
    merged["article"] = merged["Артикул"].fillna(merged["ID товара"]).astype(str).str.strip()
    merged["unit_purchase_price"] = merged["unit_purchase_price"].fillna(0).round(2)
    merged["current_stock"] = 0
    merged["avg_daily_sales"] = (merged["ожидаемый спрос в следующем месяце"] / 30).round(2)
    merged["recommended_order_qty"] = np.ceil(
        merged["ожидаемый спрос в следующем месяце"]
    ).astype(int)
    merged["recommendation_text"] = merged.apply(
        lambda row: get_recommendation_text(row.to_dict()),
        axis=1
    )

    def get_urgency(x: float) -> str:
        if x >= 15:
            return "high"
        if x >= 5:
            return "medium"
        return "low"

    merged["urgency"] = merged["ожидаемый спрос в следующем месяце"].apply(get_urgency)

    forecast_items = merged[[
        "product_id",
        "name",
        "article",
        "unit_purchase_price",
        "current_stock",
        "avg_daily_sales",
        "recommended_order_qty",
        "urgency",
        "recommendation_text",
        "ожидаемый спрос в следующем месяце",
        "ожидаемый спрос в следующем полугодии",
        "ожидаемый спрос в следующем году",
    ]].sort_values(by=["recommended_order_qty", "avg_daily_sales"],
        ascending=[False, False]
    ).reset_index(drop=True)

    summary = build_summary(
        forecast_items=forecast_items,
        cancel_rate_pct=_calculate_cancel_rate(df),
    )

    return forecast_items, summary