"""Генерация бизнес-инсайтов через GigaChat с fallback на кэш."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from gigachat import GigaChat
    _GIGACHAT_AVAILABLE = True
except ImportError:
    GigaChat = None  # type: ignore[assignment,misc]
    _GIGACHAT_AVAILABLE = False


CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "cached_insights.json"
DEFAULT_INSIGHTS: list[dict[str, str]] = [
    {
        "type": "trend",
        "title": "Выручка растёт",
        "description": (
            "Ваш бизнес показывает положительную динамику выручки. "
            "Основной канал — маркетплейсы (Ozon, Wildberries)."
        ),
        "savings": "0",
    },
    {
        "type": "warning",
        "title": "Высокая доля ФОТ",
        "description": (
            "Зарплатный фонд составляет значительную часть расходов. "
            "Рассмотрите автоматизацию рутинных процессов."
        ),
        "savings": "50000",
    },
    {
        "type": "tip",
        "title": "Оптимизируйте рекламу",
        "description": (
            "Сравните ROI по рекламным каналам. "
            "Перераспределите бюджет в пользу наиболее эффективных площадок."
        ),
        "savings": "15000",
    },
    {
        "type": "positive",
        "title": "Диверсификация каналов",
        "description": (
            "Вы продаёте через несколько маркетплейсов и соцсетей — "
            "это снижает зависимость от одного источника дохода."
        ),
        "savings": "0",
    },
    {
        "type": "anomaly",
        "title": "Проверьте крупные расходы",
        "description": (
            "Обнаружены нетипичные транзакции по расходам. "
            "Убедитесь, что все крупные списания запланированы."
        ),
        "savings": "0",
    },
]


def get_cached_insights() -> list[dict[str, str]]:
    """Возвращает инсайты из кэша или дефолтный список."""
    if CACHE_PATH.exists():
        try:
            payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, list) and payload:
                normalized: list[dict[str, str]] = []
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    normalized.append(
                        {
                            "type": str(item.get("type", "tip")),
                            "title": str(item.get("title", "Без названия")),
                            "description": str(item.get("description", "")),
                            "savings": str(item.get("savings", "0")),
                        }
                    )
                if normalized:
                    return normalized
        except Exception:
            pass

    return [item.copy() for item in DEFAULT_INSIGHTS]


def _format_expenses_block(analytics: dict[str, Any]) -> str:
    by_category = analytics.get("by_category", {})
    mom_change = analytics.get("mom_change", {})

    if not isinstance(by_category, dict) or not by_category:
        return "Нет данных по категориям"

    rows: list[str] = []
    sorted_items = sorted(by_category.items(), key=lambda item: float(item[1]), reverse=True)

    for category, amount in sorted_items[:12]:
        delta = mom_change.get(category, 0)
        delta_sign = "+" if float(delta) >= 0 else ""
        rows.append(f"- {category}: {int(round(float(amount)))}₽, {delta_sign}{int(round(float(delta)))}%")

    return "\n".join(rows)


def _format_revenue_block(analytics: dict[str, Any]) -> str:
    revenue_by_channel = analytics.get("revenue_by_channel", {})
    if not revenue_by_channel:
        return "Нет данных по каналам"

    rows: list[str] = []
    for channel, amount in sorted(revenue_by_channel.items(), key=lambda x: float(x[1]), reverse=True):
        rows.append(f"- {channel}: {int(round(float(amount)))}₽")
    return "\n".join(rows)


def _format_anomalies_block(anomalies: pd.DataFrame) -> str:
    if anomalies is None or anomalies.empty:
        return "Нет явных аномалий"

    rows: list[str] = []
    for _, row in anomalies.head(5).iterrows():
        description = str(row.get("description", ""))[:60]
        amount = float(row.get("abs_amount", 0.0))
        category = str(row.get("category", "other"))
        rows.append(f"- {description}: {int(round(amount))}₽ ({category})")

    return "\n".join(rows)


def _build_prompt(
    analytics: dict[str, Any],
    anomalies: pd.DataFrame,
    health: dict[str, Any],
    forecast: dict[str, Any],
) -> str:
    total_income = int(round(float(analytics.get("total_income", 0.0))))
    total_expenses = int(round(float(analytics.get("total_expenses", 0.0))))
    profit = int(round(float(analytics.get("profit", 0.0))))
    profit_margin = round(float(analytics.get("profit_margin", 0.0)), 1)
    burn_rate = int(round(float(analytics.get("burn_rate", 0.0))))
    runway = round(float(analytics.get("runway", 0.0)), 1)
    health_total = int(round(float(health.get("total", 0))))
    predicted_monthly = int(round(float(forecast.get("predicted_monthly", 0.0))))

    expenses_block = _format_expenses_block(analytics)
    revenue_block = _format_revenue_block(analytics)
    anomalies_block = _format_anomalies_block(anomalies)

    prompt = f"""
Ты — финансовый аналитик для малого бизнеса (ИП/ООО). Сгенерируй ровно 5 инсайтов.

БИЗНЕС-ДАННЫЕ:
Выручка: {total_income}₽, Расходы: {total_expenses}₽
Прибыль: {profit}₽, Маржа: {profit_margin}%
Burn Rate: {burn_rate}₽/мес, Runway: {runway} мес.
Health Score: {health_total}/100

РАСХОДЫ ПО КАТЕГОРИЯМ (₽, MoM %):
{expenses_block}

КАНАЛЫ ДОХОДА:
{revenue_block}

АНОМАЛИИ:
{anomalies_block}

ПРОГНОЗ РАСХОДОВ: {predicted_monthly}₽ на следующий месяц

ПРАВИЛА:
1. Ссылайся на конкретные числа из данных
2. Один позитивный инсайт обязательно
3. Давай конкретные бизнес-рекомендации (оптимизация расходов, масштабирование каналов)
4. Русский язык, кратко
5. Учитывай контекст малого бизнеса / ИП

Формат — строго по одному на строку:
тип|Заголовок|Описание 1-2 предложения|экономия в рублях/мес или 0
Типы: warning, positive, tip, anomaly, trend
""".strip()

    return prompt


def _parse_insights(raw_text: str) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []

    for line in raw_text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue

        parts = [part.strip() for part in candidate.split("|")]
        if len(parts) < 4:
            continue

        insight_type, title, description, savings = parts[:4]
        if not insight_type or not title or not description:
            continue

        insights.append(
            {
                "type": insight_type,
                "title": title,
                "description": description,
                "savings": savings,
            }
        )

    return insights


def generate_insights(
    analytics: dict[str, Any],
    anomalies: pd.DataFrame,
    health: dict[str, Any],
    forecast: dict[str, Any],
) -> list[dict[str, str]]:
    """Генерирует бизнес-инсайты через GigaChat, при ошибке — fallback на кэш."""
    credentials = os.getenv("GIGACHAT_CREDENTIALS", "").strip()
    if not credentials or not _GIGACHAT_AVAILABLE:
        return get_cached_insights()

    prompt = _build_prompt(
        analytics=analytics,
        anomalies=anomalies,
        health=health,
        forecast=forecast,
    )

    try:
        with GigaChat(
            credentials=credentials,
            verify_ssl_certs=False,
            timeout=15,
        ) as giga:
            response = giga.chat(prompt)

        choices = getattr(response, "choices", None)
        if not choices:
            return get_cached_insights()
        raw_text = str(choices[0].message.content)
        parsed = _parse_insights(raw_text)

        if len(parsed) < 3:
            return get_cached_insights()

        return parsed[:5]
    except Exception:
        return get_cached_insights()
