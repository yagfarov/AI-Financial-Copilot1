"""API роутер для AI Financial Copilot (B2B)."""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from core.analyzer import compute_analytics
from core.anomaly_detector import detect_anomalies
from core.data_loader import load_and_preprocess
from core.forecast import forecast_spending
from core.health_score import compute_health_score
from core.insights import generate_insights, get_cached_insights

router = APIRouter(prefix="/api")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# In-memory session store: session_id → combined DataFrame
_sessions: dict[str, pd.DataFrame] = {}

GLOBAL_SESSION_ID = "global"


def _init_data_dir() -> None:
    """Сканирует data/ и загружает бизнес-CSV (november, december, january, february)."""
    dfs: list[pd.DataFrame] = []
    for csv_file in sorted(DATA_DIR.glob("*.csv")):
        # Пропускаем старые демо-файлы и служебные файлы
        if csv_file.name.startswith("demo_"):
            continue
        try:
            df = load_and_preprocess(csv_file)
            dfs.append(df)
        except Exception:
            pass

    if dfs:
        combined = (
            pd.concat(dfs, ignore_index=True)
            .sort_values("date")
            .reset_index(drop=True)
        )
        _sessions[GLOBAL_SESSION_ID] = combined


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class InsightsRequest(BaseModel):
    analytics: dict[str, Any]
    anomalies: list[dict[str, Any]]
    health: dict[str, Any]
    forecast: dict[str, Any]


class ChatRequest(BaseModel):
    message: str
    context: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_anomalies(anomalies_df: pd.DataFrame) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for _, row in anomalies_df.iterrows():
        date_val = row["date"]
        date_str = str(date_val.date()) if hasattr(date_val, "date") else str(date_val)
        result.append(
            {
                "date": date_str,
                "description": str(row["description"]),
                "abs_amount": int(float(row.get("abs_amount", 0) or 0)),
                "category": str(row["category"]),
                "anomaly_reason": str(row["anomaly_reason"]),
            }
        )
    return result


def _compute_mom_kpi_delta(
    full_df: pd.DataFrame,
    current_month: str,
    current_income: int,
    current_expenses: int,
    current_profit: int,
) -> dict[str, Any]:
    """MoM дельта для KPI: доход, расходы, прибыль."""
    months = sorted(full_df["month_year"].dropna().unique().tolist())
    if current_month not in months:
        return {}

    idx = months.index(current_month)
    if idx == 0:
        return {}

    prev_month = months[idx - 1]
    prev_df = full_df[full_df["month_year"] == prev_month]
    try:
        prev = compute_analytics(prev_df)
    except Exception:
        return {}

    return {
        "income": current_income - prev["total_income"],
        "expenses": current_expenses - prev["total_expenses"],
        "profit": current_profit - prev["profit"],
    }


def _build_analytics_response_month(
    full_df: pd.DataFrame,
    month_df: pd.DataFrame,
) -> dict[str, Any]:
    """Analytics для выбранного месяца.

    - KPI, by_category, revenue_by_channel, top_transactions → month_df
    - health_score → full_df
    - anomalies: обучаем на full_df, фильтруем по месяцу
    - forecast: по full_df
    """
    analytics = compute_analytics(month_df)
    analytics.pop("daily_expenses")

    full_analytics = compute_analytics(full_df)
    full_daily: pd.Series = full_analytics.pop("daily_expenses")

    health = compute_health_score(full_analytics)

    # Аномалии: обучаем на full_df, показываем за месяц
    all_anomalies = detect_anomalies(full_df)
    if not all_anomalies.empty and len(month_df) > 0:
        target_month = month_df["month_year"].iloc[0]
        anom_months = pd.to_datetime(all_anomalies["date"]).dt.strftime("%Y-%m")
        all_anomalies = (
            all_anomalies[anom_months == target_month]
            .head(5)
            .reset_index(drop=True)
        )

    forecast = forecast_spending(full_daily)

    by_category = {k: v for k, v in analytics["by_category"].items() if v > 0}

    target_month = month_df["month_year"].iloc[0] if not month_df.empty else ""
    mom_kpi_delta = _compute_mom_kpi_delta(
        full_df,
        target_month,
        analytics["total_income"],
        analytics["total_expenses"],
        analytics["profit"],
    )

    return {
        "total_income": analytics["total_income"],
        "total_expenses": analytics["total_expenses"],
        "profit": analytics["profit"],
        "profit_margin": analytics["profit_margin"],
        "burn_rate": analytics["burn_rate"],
        "runway": analytics["runway"],
        "mom_kpi_delta": mom_kpi_delta,
        "health_score": health,
        "by_category": by_category,
        "by_category_pct": analytics["by_category_pct"],
        "revenue_by_channel": analytics["revenue_by_channel"],
        "monthly_income": full_analytics["monthly_income"],
        "monthly_expenses": full_analytics["monthly_expenses"],
        "top_transactions": analytics["top_transactions"],
        "anomalies": _serialize_anomalies(all_anomalies),
        "forecast": forecast,
    }


def _pick_default_month(df: pd.DataFrame) -> str:
    """Последний месяц с доходом."""
    months = sorted(df["month_year"].dropna().unique().tolist(), reverse=True)
    income_df = df[df["type"] == "income"]
    if not income_df.empty:
        months_with_income = set(income_df["month_year"].dropna().unique())
        for m in months:
            if m in months_with_income:
                return m
    return months[0]


def _load_csv_files(files: list[UploadFile]) -> pd.DataFrame:
    dfs: list[pd.DataFrame] = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".csv"):
            raise ValueError(f"«{f.filename}»: ожидается CSV-файл")
        raw = f.file.read()
        buf = io.BytesIO(raw)
        df = load_and_preprocess(buf)
        dfs.append(df)

    combined = (
        pd.concat(dfs, ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )
    return combined


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/init")
def get_init() -> dict[str, Any]:
    """Данные из глобальной сессии (авто-загрузка из data/)."""
    df = _sessions.get(GLOBAL_SESSION_ID)

    if df is None or df.empty:
        return {"empty": True, "months": []}

    months = sorted(df["month_year"].dropna().unique().tolist(), reverse=True)
    default_month = _pick_default_month(df)
    month_df = df[df["month_year"] == default_month]

    try:
        data = _build_analytics_response_month(df, month_df)
    except Exception as exc:
        return {"empty": True, "months": [], "error": str(exc)}

    return {"session_id": GLOBAL_SESSION_ID, "months": months, "default_month": default_month, "empty": False, **data}


@router.post("/upload")
def upload_csv(
    files: Annotated[list[UploadFile], File()],
    session_id: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    """Загрузка CSV. Merge с сессией если session_id передан."""
    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов для загрузки")

    try:
        new_df = _load_csv_files(files)

        existing_df = _sessions.get(session_id) if session_id else None
        if existing_df is not None and not existing_df.empty:
            combined = (
                pd.concat([existing_df, new_df], ignore_index=True)
                .sort_values("date")
                .reset_index(drop=True)
            )
            new_session_id = session_id
        else:
            combined = new_df
            new_session_id = str(uuid.uuid4())

        _sessions[new_session_id] = combined

        months = sorted(combined["month_year"].dropna().unique().tolist(), reverse=True)
        default_month = _pick_default_month(combined) if months else None

        if default_month:
            month_df = combined[combined["month_year"] == default_month]
            data = _build_analytics_response_month(combined, month_df)
        else:
            data = _build_analytics_response_month(combined, combined)

        return {"session_id": new_session_id, "months": months, "default_month": default_month, **data}

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {exc}") from exc


@router.get("/metrics/{session_id}")
def get_metrics(session_id: str) -> dict[str, Any]:
    """Основные бизнес-метрики по всей истории."""
    combined = _sessions.get(session_id)
    if combined is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    try:
        analytics = compute_analytics(combined)
        analytics.pop("daily_expenses")
        health = compute_health_score(analytics)
        return {
            "total_income": analytics["total_income"],
            "total_expenses": analytics["total_expenses"],
            "profit": analytics["profit"],
            "profit_margin": analytics["profit_margin"],
            "burn_rate": analytics["burn_rate"],
            "runway": analytics["runway"],
            "health_score": health,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/analytics/{session_id}")
def get_month_analytics(session_id: str, month: str) -> dict[str, Any]:
    """Аналитика за конкретный месяц."""
    combined = _sessions.get(session_id)
    if combined is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена — перезагрузите данные")

    month_df = combined[combined["month_year"] == month]
    if month_df.empty:
        raise HTTPException(status_code=404, detail=f"Нет транзакций за {month}")

    try:
        return _build_analytics_response_month(combined, month_df)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка: {exc}") from exc


@router.get("/forecast/{session_id}")
def get_forecast(session_id: str) -> dict[str, Any]:
    """Прогноз расходов на 1-2 месяца."""
    combined = _sessions.get(session_id)
    if combined is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    try:
        analytics = compute_analytics(combined)
        daily = analytics["daily_expenses"]
        forecast_30 = forecast_spending(daily, days_ahead=30)
        forecast_60 = forecast_spending(daily, days_ahead=60)
        return {"forecast_30d": forecast_30, "forecast_60d": forecast_60}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/insights")
def get_insights(body: InsightsRequest) -> dict[str, Any]:
    """Генерация бизнес-инсайтов через GigaChat."""
    try:
        anomalies_df = pd.DataFrame(body.anomalies)
        insights = generate_insights(
            analytics=body.analytics,
            anomalies=anomalies_df,
            health=body.health,
            forecast=body.forecast,
        )
        return {"insights": insights}
    except Exception as exc:
        try:
            return {"insights": get_cached_insights()}
        except Exception:
            raise HTTPException(status_code=500, detail=f"Ошибка: {exc}") from exc


@router.get("/agent")
def agent_stub() -> dict[str, Any]:
    """RAG-заглушка. Архитектура готова к подключению vector DB."""
    return {
        "status": "coming_soon",
        "message": (
            "Я финансовый ассистент вашего бизнеса. "
            "Интеграция базы знаний (RAG) находится в разработке. "
            "Скоро вы сможете загружать документы и задавать вопросы в свободной форме."
        ),
        "capabilities": [
            "Анализ договоров и счетов",
            "Ответы на вопросы по финансовой отчётности",
            "Рекомендации на основе базы знаний",
        ],
    }


@router.post("/chat")
def chat(body: ChatRequest) -> dict[str, Any]:
    """Чат с финансовым ассистентом."""
    ctx = body.context

    top_categories_raw = ctx.get("by_category", {})
    if isinstance(top_categories_raw, dict):
        top_3 = sorted(top_categories_raw.items(), key=lambda x: float(x[1]), reverse=True)[:3]
        top_categories_str = ", ".join(f"{cat}: {amt}₽" for cat, amt in top_3)
    else:
        top_categories_str = "нет данных"

    forecast = ctx.get("forecast", {})
    predicted_monthly = forecast.get("predicted_monthly", 0) if isinstance(forecast, dict) else 0

    health = ctx.get("health_score", {})
    health_total = health.get("total", 0) if isinstance(health, dict) else 0

    profit = ctx.get("profit", 0)
    burn_rate = ctx.get("burn_rate", 0)

    prompt = (
        "Ты — финансовый аналитик для малого бизнеса (ИП/ООО). Отвечай кратко, по-русски, используя данные.\n\n"
        "БИЗНЕС-КОНТЕКСТ:\n"
        f"Выручка: {ctx.get('total_income', 0)}₽, "
        f"Расходы: {ctx.get('total_expenses', 0)}₽, "
        f"Прибыль: {profit}₽\n"
        f"Burn Rate: {burn_rate}₽/мес\n"
        f"Health Score: {health_total}/100\n"
        f"Топ расходы: {top_categories_str}\n"
        f"Прогноз расходов: {predicted_monthly}₽\n\n"
        f"ВОПРОС: {body.message}"
    )

    credentials = os.getenv("GIGACHAT_CREDENTIALS", "").strip()

    if credentials:
        try:
            from gigachat import GigaChat  # noqa: PLC0415

            with GigaChat(credentials=credentials, verify_ssl_certs=False, timeout=20) as giga:
                response = giga.chat(prompt)

            choices = getattr(response, "choices", None)
            if choices:
                reply = str(choices[0].message.content)
                return {"reply": reply}
        except Exception:
            pass

    stub = (
        f"Выручка вашего бизнеса: {ctx.get('total_income', 0)}₽, "
        f"расходы: {ctx.get('total_expenses', 0)}₽, "
        f"прибыль: {profit}₽. "
        f"Health Score: {health_total}/100. "
        "GigaChat временно недоступен — подключите API ключ для детального анализа."
    )
    return {"reply": stub}
