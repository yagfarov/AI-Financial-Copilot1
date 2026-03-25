"""Прогноз расходов на основе скользящего среднего."""

from __future__ import annotations

from typing import Any

import pandas as pd


def forecast_spending(daily_expenses: pd.Series, days_ahead: int = 30) -> dict[str, Any]:
    """Прогнозирует траты на горизонте `days_ahead` дней.

    Метод:
    - Берётся окно последних 30 наблюдений дневных расходов.
    - Вычисляются среднее и стандартное отклонение по окну.
    - Прогноз на горизонт = mean * days_ahead.
    - Доверительный интервал = (mean ± 1*std) * days_ahead.

    Args:
        daily_expenses: Series дневных расходов с индексом даты.
        days_ahead: Горизонт прогноза в днях.

    Returns:
        Словарь вида:
        {
            'predicted_monthly': float,
            'avg_daily': float,
            'confidence_low': float,
            'confidence_high': float,
        }
    """
    if days_ahead <= 0:
        raise ValueError("days_ahead должен быть положительным числом.")

    if daily_expenses is None or daily_expenses.empty:
        return {
            "predicted_monthly": 0.0,
            "avg_daily": 0.0,
            "confidence_low": 0.0,
            "confidence_high": 0.0,
        }

    series = daily_expenses.copy()
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return {
            "predicted_monthly": 0.0,
            "avg_daily": 0.0,
            "confidence_low": 0.0,
            "confidence_high": 0.0,
        }

    # Упорядочиваем по времени, заполняем пропуски нулями и берём последние 30 календарных дней.
    series = series.sort_index()
    if hasattr(series.index, "tz") and series.index.tz is not None:
        series.index = series.index.tz_localize(None)
    full_range = pd.date_range(series.index.min(), series.index.max(), freq="D")
    series = series.reindex(full_range, fill_value=0.0)
    rolling_window = series.tail(30)

    mean_value = float(rolling_window.mean())
    std_value = float(rolling_window.std(ddof=0))

    predicted_monthly = mean_value * days_ahead
    confidence_low = max(0.0, (mean_value - std_value) * days_ahead)
    confidence_high = (mean_value + std_value) * days_ahead

    return {
        "predicted_monthly": round(predicted_monthly, 2),
        "avg_daily": round(mean_value, 2),
        "confidence_low": round(confidence_low, 2),
        "confidence_high": round(confidence_high, 2),
    }
