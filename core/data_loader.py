"""Загрузка и предобработка бизнес-транзакций из CSV."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any

import pandas as pd


FileInput = str | Path | IO[str] | IO[bytes] | Any
REQUIRED_COLUMNS: tuple[str, ...] = ("date", "amount", "type", "category", "description")


def _read_csv(file: FileInput) -> pd.DataFrame:
    """Читает CSV из пути или файлового объекта."""
    if isinstance(file, (str, Path)):
        return pd.read_csv(file)

    if hasattr(file, "seek"):
        try:
            file.seek(0)
        except Exception:
            pass

    return pd.read_csv(file)


def load_and_preprocess(file: FileInput) -> pd.DataFrame:
    """Загружает CSV бизнес-транзакций и добавляет аналитические колонки.

    Формат CSV: date, amount, type, category, description
    - amount > 0 всегда
    - type: income / expense

    Returns:
        pd.DataFrame с доп. колонками:
            - abs_amount: = amount (для совместимости с ML-моделями)
            - month: YYYY-MM
            - month_year: YYYY-MM (алиас)
            - day_of_week: 0=пн ... 6=вс
            - is_weekend: bool
    """
    df = _read_csv(file)

    if df.empty:
        raise ValueError("CSV пустой: не найдено ни одной транзакции.")

    prepared = df.copy()

    # Нормализуем имена колонок
    prepared.columns = prepared.columns.str.strip().str.lower()

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in prepared.columns]
    if missing_columns:
        raise ValueError(
            f"CSV должен содержать колонки: {', '.join(REQUIRED_COLUMNS)}. "
            f"Отсутствуют: {', '.join(missing_columns)}."
        )

    # Валидация date
    original_dates = prepared["date"].copy()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    invalid_dates = prepared["date"].isna()
    if invalid_dates.any():
        samples = original_dates[invalid_dates].astype(str).head(5).tolist()
        raise ValueError(f"Колонка 'date' содержит некорректные значения. Примеры: {samples}.")

    # Валидация amount
    original_amounts = prepared["amount"].copy()
    prepared["amount"] = pd.to_numeric(prepared["amount"], errors="coerce")
    invalid_amounts = prepared["amount"].isna()
    if invalid_amounts.any():
        samples = original_amounts[invalid_amounts].astype(str).head(5).tolist()
        raise ValueError(f"Колонка 'amount' содержит нечисловые значения. Примеры: {samples}.")

    # Нормализация type
    prepared["type"] = prepared["type"].astype(str).str.strip().str.lower()
    valid_types = {"income", "expense"}
    invalid_types = ~prepared["type"].isin(valid_types)
    if invalid_types.any():
        samples = prepared.loc[invalid_types, "type"].head(5).tolist()
        raise ValueError(f"Колонка 'type' содержит недопустимые значения. Примеры: {samples}. Допустимые: income, expense.")

    # Нормализация category и description
    prepared["category"] = prepared["category"].fillna("other").astype(str).str.strip()
    prepared["description"] = prepared["description"].fillna("").astype(str).str.strip()

    # Производные колонки
    prepared["abs_amount"] = prepared["amount"].abs()
    prepared["month"] = prepared["date"].dt.strftime("%Y-%m")
    prepared["month_year"] = prepared["month"]
    prepared["day_of_week"] = prepared["date"].dt.dayofweek
    prepared["is_weekend"] = prepared["day_of_week"] >= 5

    prepared = prepared.sort_values("date", ascending=True).reset_index(drop=True)
    return prepared
