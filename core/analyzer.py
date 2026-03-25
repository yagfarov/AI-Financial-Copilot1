"""Бизнес-аналитика: метрики, агрегации, MoM-изменения."""

from __future__ import annotations

from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "date",
    "amount",
    "description",
    "type",
    "abs_amount",
    "month",
    "day_of_week",
    "is_weekend",
    "category",
}


def _round_int(value: float) -> int:
    return int(round(float(value)))


def _normalize_type(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


def _safe_ratio(numerator: float, denominator: float, digits: int = 1) -> float:
    if denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator), digits)


def compute_analytics(df: pd.DataFrame) -> dict[str, Any]:
    """Бизнес-аналитика из DataFrame транзакций.

    Возвращает:
        - total_income, total_expenses, profit, profit_margin
        - burn_rate, runway
        - by_category (расходы), by_category_pct
        - revenue_by_channel (доходы по категориям)
        - monthly_income, monthly_expenses (для графиков)
        - mom_change (MoM по категориям расходов)
        - top_transactions (топ-5 расходов)
        - daily_expenses (Series для forecast)
    """
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing_columns))}")

    if df.empty:
        empty_series = pd.Series(dtype="float64")
        return {
            "total_income": 0,
            "total_expenses": 0,
            "profit": 0,
            "profit_margin": 0.0,
            "burn_rate": 0,
            "runway": 0.0,
            "by_category": {},
            "by_category_pct": {},
            "revenue_by_channel": {},
            "monthly_income": {},
            "monthly_expenses": {},
            "mom_change": {},
            "top_transactions": [],
            "weekend_ratio": 0.0,
            "daily_expenses": empty_series,
        }

    work_df = df.copy()
    work_df["type_norm"] = _normalize_type(work_df["type"])

    income_df = work_df[work_df["type_norm"] == "income"]
    expense_df = work_df[work_df["type_norm"] == "expense"]

    total_income = float(income_df["amount"].sum())
    total_expenses = float(expense_df["amount"].sum())
    profit = total_income - total_expenses
    profit_margin = _safe_ratio(profit, total_income, digits=1) * 100 if total_income > 0 else 0.0

    # Burn Rate = средние месячные расходы
    monthly_exp_series = expense_df.groupby("month")["amount"].sum()
    burn_rate = _round_int(monthly_exp_series.mean()) if not monthly_exp_series.empty else 0

    # Runway = accumulated profit / avg monthly expenses
    if burn_rate > 0 and profit > 0:
        runway = round(profit / burn_rate, 1)
    else:
        runway = 0.0

    # Расходы по категориям
    by_category_series = expense_df.groupby("category")["amount"].sum().sort_values(ascending=False)
    by_category = {str(cat): _round_int(val) for cat, val in by_category_series.items()}

    if total_expenses == 0:
        by_category_pct = {str(cat): 0 for cat in by_category_series.index}
    else:
        by_category_pct = {
            str(cat): _round_int((float(val) / total_expenses) * 100)
            for cat, val in by_category_series.items()
        }

    # Доходы по каналам (извлекаем название площадки из description)
    income_work = income_df.copy()
    income_work["channel"] = (
        income_work["description"]
        .str.split("—").str[0]
        .str.strip()
    )
    # Fallback на category, если описание не содержит " — "
    income_work.loc[income_work["channel"] == "", "channel"] = income_work["category"]
    rev_by_channel = income_work.groupby("channel")["amount"].sum().sort_values(ascending=False)
    revenue_by_channel = {str(ch): _round_int(val) for ch, val in rev_by_channel.items()}

    # Помесячные доходы и расходы (для графиков)
    monthly_income_series = income_df.groupby("month")["amount"].sum().sort_index()
    monthly_income = {str(m): _round_int(v) for m, v in monthly_income_series.items()}

    monthly_expenses_series = expense_df.groupby("month")["amount"].sum().sort_index()
    monthly_expenses = {str(m): _round_int(v) for m, v in monthly_expenses_series.items()}

    # MoM по категориям расходов
    unique_months = pd.Series(expense_df["month"].dropna().unique())
    if len(unique_months) < 2:
        mom_change: dict[str, int] = {}
    else:
        ordered_months = sorted(unique_months.tolist())
        previous_month = ordered_months[-2]
        last_month = ordered_months[-1]

        prev_cat = expense_df[expense_df["month"] == previous_month].groupby("category")["amount"].sum()
        last_cat = expense_df[expense_df["month"] == last_month].groupby("category")["amount"].sum()

        mom_change = {}
        all_categories = sorted(set(prev_cat.index).union(set(last_cat.index)))
        for category in all_categories:
            prev_value = float(prev_cat.get(category, 0.0))
            last_value = float(last_cat.get(category, 0.0))
            if prev_value == 0:
                pct_change = 0.0 if last_value == 0 else 100.0
            else:
                pct_change = ((last_value - prev_value) / prev_value) * 100
            mom_change[str(category)] = _round_int(pct_change)

    # Топ-5 расходов
    top_expenses = expense_df.sort_values("amount", ascending=False).head(5)
    top_transactions = [
        {
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "description": row["description"],
            "abs_amount": _round_int(row["amount"]),
            "category": row["category"],
        }
        for _, row in top_expenses.iterrows()
    ]

    # Weekend ratio
    weekend_avg = float(expense_df[expense_df["is_weekend"] == True]["amount"].mean())  # noqa: E712
    weekday_avg = float(expense_df[expense_df["is_weekend"] == False]["amount"].mean())  # noqa: E712
    if pd.isna(weekend_avg):
        weekend_avg = 0.0
    if pd.isna(weekday_avg):
        weekday_avg = 0.0
    weekend_ratio = _safe_ratio(weekend_avg, weekday_avg, digits=1)

    # Daily expenses для forecast
    daily_expenses = (
        expense_df.assign(date=pd.to_datetime(expense_df["date"]).dt.normalize())
        .groupby("date")["amount"]
        .sum()
        .sort_index()
    )

    return {
        "total_income": _round_int(total_income),
        "total_expenses": _round_int(total_expenses),
        "profit": _round_int(profit),
        "profit_margin": round(profit_margin, 1),
        "burn_rate": burn_rate,
        "runway": runway,
        "by_category": by_category,
        "by_category_pct": by_category_pct,
        "revenue_by_channel": revenue_by_channel,
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "mom_change": mom_change,
        "top_transactions": top_transactions,
        "weekend_ratio": weekend_ratio,
        "daily_expenses": daily_expenses,
    }
