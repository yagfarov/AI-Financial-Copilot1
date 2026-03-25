"""Обнаружение аномальных расходных транзакций."""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


REQUIRED_COLUMNS: Final[set[str]] = {
    "date",
    "amount",
    "description",
    "type",
    "abs_amount",
    "category",
    "day_of_week",
    "is_weekend",
}

MIN_EXPENSES_FOR_DETECTION: Final[int] = 10


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["date", "description", "abs_amount", "category", "anomaly_reason"]
    )


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Определяет аномальные расходы через Isolation Forest.

    Обучается на всех расходах. Возвращает все найденные аномалии
    (фильтрация по месяцу — на уровне приложения).
    """
    missing_columns = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(
            f"Отсутствуют обязательные колонки: {', '.join(missing_columns)}."
        )

    work_df = df.copy()
    work_df["type"] = work_df["type"].astype(str).str.strip().str.lower()

    expenses = work_df[work_df["type"] == "expense"].copy()
    if len(expenses) < MIN_EXPENSES_FOR_DETECTION:
        return _empty_result()

    expenses["abs_amount"] = pd.to_numeric(expenses["abs_amount"], errors="coerce")
    expenses["day_of_week"] = pd.to_numeric(expenses["day_of_week"], errors="coerce")
    expenses["is_weekend"] = expenses["is_weekend"].astype(int)

    expenses = expenses.dropna(subset=["abs_amount", "day_of_week", "category", "description", "date"])
    if len(expenses) < MIN_EXPENSES_FOR_DETECTION:
        return _empty_result()

    category_stats = expenses.groupby("category")["abs_amount"].agg(["mean", "std"]).rename(
        columns={"mean": "cat_mean", "std": "cat_std"}
    )
    expenses = expenses.join(category_stats, on="category")

    expenses["ratio_to_cat_mean"] = np.where(
        expenses["cat_mean"] > 0,
        expenses["abs_amount"] / expenses["cat_mean"],
        0.0,
    )

    cat_std = expenses["cat_std"].clip(lower=1.0)
    expenses["z_score"] = (expenses["abs_amount"] - expenses["cat_mean"]) / cat_std
    expenses["z_score"] = expenses["z_score"].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    features = expenses[
        ["abs_amount", "ratio_to_cat_mean", "z_score", "day_of_week", "is_weekend"]
    ].copy()

    model = IsolationForest(
        contamination=0.05,
        random_state=42,
        n_estimators=100,
    )
    predictions = model.fit_predict(features)
    expenses["is_anomaly"] = predictions == -1

    anomalies = expenses[expenses["is_anomaly"]].copy()
    if anomalies.empty:
        return _empty_result()

    def build_reason(row: pd.Series) -> str:
        ratio = float(row["ratio_to_cat_mean"])
        category = str(row["category"])
        if ratio > 3:
            return f"Сумма в {ratio:.1f}x выше средней по категории «{category}»"
        return "Необычная транзакция по совокупности признаков"

    anomalies["anomaly_reason"] = anomalies.apply(build_reason, axis=1)

    result = anomalies[["date", "description", "abs_amount", "category", "anomaly_reason"]].copy()
    result["abs_amount"] = result["abs_amount"].round().astype(int)

    result = result.sort_values("abs_amount", ascending=False).reset_index(drop=True)
    return result
