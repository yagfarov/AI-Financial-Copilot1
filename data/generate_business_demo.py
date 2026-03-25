"""Генератор демо-данных для B2B Financial Copilot — ИП по производству мармелада."""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

OUTPUT_DIR = Path(__file__).parent

# === Шаблоны транзакций ===

INCOME_TEMPLATES = [
    # (description, category, min_amount, max_amount, freq_per_month)
    ("Ozon — заказ мармелад ассорти", "маркетплейсы", 8000, 45000, 8),
    ("Ozon — заказ мармелад премиум", "маркетплейсы", 12000, 55000, 5),
    ("Wildberries — продажи мармелад", "маркетплейсы", 6000, 40000, 7),
    ("Wildberries — заказ подарочный набор", "маркетплейсы", 15000, 60000, 3),
    ("Яндекс Лавка — поставка мармелад", "маркетплейсы", 5000, 25000, 4),
    ("Яндекс Маркет — заказ", "маркетплейсы", 10000, 35000, 3),
    ("Instagram — прямые продажи", "соцсети", 3000, 18000, 4),
    ("VK — заказ через сообщество", "соцсети", 2000, 12000, 3),
    ("Telegram — заказ оптовый", "соцсети", 8000, 30000, 2),
]

EXPENSE_TEMPLATES = {
    "зарплата": [
        ("Зарплата — Иванов А.С. (производство)", 55000, 55000),
        ("Зарплата — Петрова Н.В. (упаковка)", 42000, 42000),
        ("Зарплата — Сидоров К.М. (логистика)", 48000, 48000),
        ("Зарплата — Козлова Е.А. (маркетинг)", 50000, 50000),
        ("Зарплата — Морозов Д.И. (производство)", 45000, 45000),
    ],
    "реклама": [
        ("Яндекс Директ — рекламная кампания", 8000, 35000),
        ("VK Ads — таргетированная реклама", 5000, 20000),
        ("Instagram — продвижение постов", 3000, 15000),
        ("Блогер — интеграция у food-блогера", 10000, 40000),
        ("Ozon — продвижение товаров", 5000, 25000),
        ("Wildberries — реклама в каталоге", 4000, 18000),
    ],
    "SaaS": [
        ("AmoCRM — подписка", 4990, 4990),
        ("Zoom — бизнес-тариф", 1990, 1990),
        ("1С:Бухгалтерия — облако", 6500, 6500),
        ("Битрикс24 — тариф Стандартный", 5590, 5590),
        ("Canva Pro — дизайн", 1290, 1290),
        ("Google Workspace — почта и диск", 1590, 1590),
    ],
    "оборудование": [
        ("Формы для мармелада — закупка", 8000, 35000),
        ("Упаковочный материал — коробки", 5000, 25000),
        ("Пищевые красители и ароматизаторы", 10000, 40000),
        ("Сырье — желатин, пектин, сахар", 15000, 60000),
        ("Термометры и весы — калибровка", 3000, 8000),
        ("Этикетки и стикеры", 4000, 15000),
    ],
    "логистика": [
        ("CDEK — отправка заказов", 3000, 15000),
        ("Boxberry — доставка", 2000, 12000),
        ("Яндекс Такси — деловые поездки", 800, 3500),
        ("Топливо — служебный автомобиль", 3000, 6000),
        ("Почта России — отправка", 1500, 8000),
        ("DPD — доставка крупных заказов", 4000, 18000),
    ],
    "коммунальные услуги": [
        ("Аренда производственного помещения", 45000, 45000),
        ("Электроэнергия — производство", 8000, 15000),
        ("Водоснабжение", 3000, 5000),
        ("Интернет — Ростелеком бизнес", 2500, 2500),
        ("Вывоз отходов — Экосервис", 3500, 3500),
    ],
}

# === Сезонные множители ===
SEASON = {
    11: {"income": 1.15, "expense": 0.95},  # ноябрь — нормальный месяц, небольшой плюс
    12: {"income": 1.7, "expense": 1.1},    # декабрь — пик (Новый год)
    1:  {"income": 0.65, "expense": 0.75},  # январь — спад, но и расходы ниже
    2:  {"income": 1.0, "expense": 0.88},   # февраль — восстановление
}


def _random_dates(year: int, month: int, count: int) -> list[date]:
    """Генерирует count случайных дат в заданном месяце."""
    if month == 12:
        days_in_month = 31
    elif month == 1:
        days_in_month = 31
    elif month == 2:
        days_in_month = 28
    elif month == 11:
        days_in_month = 30
    else:
        days_in_month = 30

    return sorted(
        date(year, month, random.randint(1, days_in_month))
        for _ in range(count)
    )


def generate_month(year: int, month: int) -> list[dict]:
    """Генерирует транзакции за один месяц."""
    season = SEASON[month]
    rows = []

    # --- Доходы ---
    for desc, cat, lo, hi, freq in INCOME_TEMPLATES:
        adjusted_freq = max(1, int(freq * season["income"] + random.uniform(-0.5, 0.5)))
        dates = _random_dates(year, month, adjusted_freq)
        for d in dates:
            amount = int(random.uniform(lo, hi) * season["income"])
            # Добавляем ±10% шума
            amount = int(amount * random.uniform(0.9, 1.1))
            rows.append({
                "date": d.isoformat(),
                "amount": amount,
                "type": "income",
                "category": cat,
                "description": desc,
            })

    # --- Расходы ---
    for cat, templates in EXPENSE_TEMPLATES.items():
        for desc, lo, hi in templates:
            # Зарплата — 1 раз в месяц, фиксированная
            if cat == "зарплата":
                pay_date = date(year, month, random.choice([5, 10, 15]))
                amount = lo  # фиксированная зарплата
                rows.append({
                    "date": pay_date.isoformat(),
                    "amount": amount,
                    "type": "expense",
                    "category": cat,
                    "description": desc,
                })
                continue

            # SaaS — 1 раз в месяц
            if cat == "SaaS":
                saas_date = date(year, month, random.randint(1, 5))
                rows.append({
                    "date": saas_date.isoformat(),
                    "amount": lo,
                    "type": "expense",
                    "category": cat,
                    "description": desc,
                })
                continue

            # Коммунальные — 1 раз в месяц
            if cat == "коммунальные услуги":
                util_date = date(year, month, random.randint(1, 10))
                amount = int(random.uniform(lo, hi) * season["expense"])
                rows.append({
                    "date": util_date.isoformat(),
                    "amount": amount,
                    "type": "expense",
                    "category": cat,
                    "description": desc,
                })
                continue

            # Реклама — 1-3 раза в месяц
            if cat == "реклама":
                freq = random.randint(1, 3)
                dates = _random_dates(year, month, freq)
                for d in dates:
                    amount = int(random.uniform(lo, hi) * season["expense"])
                    rows.append({
                        "date": d.isoformat(),
                        "amount": amount,
                        "type": "expense",
                        "category": cat,
                        "description": desc,
                    })
                continue

            # Оборудование — 1-2 раза в месяц
            if cat == "оборудование":
                freq = random.randint(1, 2)
                dates = _random_dates(year, month, freq)
                for d in dates:
                    amount = int(random.uniform(lo, hi) * season["expense"])
                    rows.append({
                        "date": d.isoformat(),
                        "amount": amount,
                        "type": "expense",
                        "category": cat,
                        "description": desc,
                    })
                continue

            # Логистика — 2-5 раз в месяц
            if cat == "логистика":
                freq = random.randint(2, 5)
                dates = _random_dates(year, month, freq)
                for d in dates:
                    amount = int(random.uniform(lo, hi) * season["expense"])
                    rows.append({
                        "date": d.isoformat(),
                        "amount": amount,
                        "type": "expense",
                        "category": cat,
                        "description": desc,
                    })

    # Сортируем по дате
    rows.sort(key=lambda r: r["date"])
    return rows


def write_csv(rows: list[dict], filename: str) -> None:
    """Записывает транзакции в CSV."""
    path = OUTPUT_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "amount", "type", "category", "description"])
        writer.writeheader()
        writer.writerows(rows)

    total_income = sum(r["amount"] for r in rows if r["type"] == "income")
    total_expense = sum(r["amount"] for r in rows if r["type"] == "expense")
    print(f"{filename}: {len(rows)} транзакций | Доход: {total_income:,}₽ | Расход: {total_expense:,}₽ | Прибыль: {total_income - total_expense:,}₽")


if __name__ == "__main__":
    write_csv(generate_month(2025, 11), "november.csv")
    write_csv(generate_month(2025, 12), "december.csv")
    write_csv(generate_month(2026, 1), "january.csv")
    write_csv(generate_month(2026, 2), "february.csv")
    print("\nГотово!")
