"""Business Financial Health Score (0–100)."""

from __future__ import annotations

from typing import Any


def _score_profit_margin(margin: float) -> int:
    """Оценка маржинальности бизнеса."""
    if margin >= 20:
        return 100
    if margin >= 10:
        return 70
    if margin >= 0:
        return 40
    return 10


def _score_revenue_stability(cv: float) -> int:
    """Оценка стабильности выручки (коэффициент вариации)."""
    if cv < 0.15:
        return 100
    if cv < 0.30:
        return 70
    if cv < 0.50:
        return 40
    return 10


def _score_cost_structure(fixed_ratio: float) -> int:
    """Оценка доли фиксированных расходов (зарплата + коммуналка)."""
    if fixed_ratio < 50:
        return 100
    if fixed_ratio < 65:
        return 70
    if fixed_ratio < 80:
        return 40
    return 10


def _clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def compute_health_score(analytics: dict[str, Any]) -> dict[str, Any]:
    """Вычисляет Business Health Score.

    Компоненты:
    - Profit margin (35%) — маржинальность
    - Revenue stability (30%) — стабильность выручки по месяцам
    - Cost structure (35%) — доля фиксированных расходов
    """
    profit_margin = float(analytics.get("profit_margin", 0.0))

    # Revenue stability: CV по месячным доходам
    monthly_income = analytics.get("monthly_income", {})
    income_values = [float(v) for v in monthly_income.values()]
    if len(income_values) >= 2:
        mean_income = sum(income_values) / len(income_values)
        if mean_income == 0:
            cv = 0.0
        else:
            variance = sum((v - mean_income) ** 2 for v in income_values) / len(income_values)
            cv = (variance ** 0.5) / mean_income
    else:
        cv = 0.0

    # Cost structure: доля зарплаты + коммуналки в общих расходах
    total_expenses = float(analytics.get("total_expenses", 0.0))
    by_category = analytics.get("by_category", {})

    # Фиксированные расходы: зарплата + коммунальные услуги
    fixed_total = float(by_category.get("зарплата", 0.0))
    fixed_total += float(by_category.get("коммунальные услуги", 0.0))

    if total_expenses <= 0:
        fixed_ratio = 0.0
    else:
        fixed_ratio = (fixed_total / total_expenses) * 100

    margin_score = _score_profit_margin(profit_margin)
    stability_score = _score_revenue_stability(cv)
    cost_score = _score_cost_structure(fixed_ratio)

    total_score = _clamp_score(
        0.35 * margin_score
        + 0.30 * stability_score
        + 0.35 * cost_score
    )

    return {
        "total": total_score,
        "components": {
            "profit_margin": {
                "score": margin_score,
                "value": round(profit_margin, 1),
                "label": "Маржинальность",
            },
            "revenue_stability": {
                "score": stability_score,
                "value": round(cv, 3),
                "label": "Стабильность выручки",
            },
            "cost_structure": {
                "score": cost_score,
                "value": round(fixed_ratio, 1),
                "label": "Доля фикс. расходов",
            },
        },
    }
