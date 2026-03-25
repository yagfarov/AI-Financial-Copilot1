# AI Financial Copilot — B2B

**Финансовая аналитика для малого бизнеса** — ИП, самозанятые, ООО. Загрузите CSV-выписки и получите бизнес-метрики, прогнозы, аномалии и AI-рекомендации.

> Демо-кейс: ИП по производству мармелада — маркетплейсы, соцсети, производство.

---

## Оглавление

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Технологии](#технологии)
- [Быстрый старт](#быстрый-старт)
- [Формат данных](#формат-данных)
- [Структура проекта](#структура-проекта)
- [Описание модулей](#описание-модулей)
- [Roadmap](#roadmap)
- [Команда](#команда)

---

## Возможности

### Dashboard
4 KPI-карточки (Выручка, Расходы, Прибыль, Health Score) с MoM-дельтами. Графики: помесячный revenue vs expenses, структура расходов по категориям, каналы выручки. Бизнес-метрики: маржинальность, burn rate, runway, прогноз.

### Analytics
Детальная таблица расходов по категориям с MoM%, топ-транзакции, обнаруженные аномалии (Isolation Forest), AI-инсайты от GigaChat.

### AI Agent
RAG-ready заглушка с чатом. Контекст бизнес-метрик передаётся в GigaChat для релевантных ответов.

### Ключевые метрики
- **Прибыль и маржинальность** — profit margin по месяцам
- **Burn Rate** — средний уровень расходов в месяц
- **Runway** — накопленная прибыль / средние месячные расходы
- **Revenue by Channel** — выручка в разрезе каналов (маркетплейсы, соцсети и др.)
- **Health Score (0–100)** — profit margin (35%) + revenue stability (30%) + cost structure (35%)

### Темы оформления
Dark theme (по умолчанию) с glassmorphism + light theme. Toggle сохраняется в localStorage.

---

## Архитектура

```
┌─────────────────────────────────┐
│  CSV файлы (по месяцам)         │  drag-and-drop upload
└───────────────┬─────────────────┘
                ▼
┌─────────────────────────────────┐
│  Data Loader                    │  Валидация, нормализация,
│  (Pandas)                       │  производные признаки
└───────────────┬─────────────────┘
                ▼
┌─────────────────────────────────┐
│  FastAPI Backend                │
│                                 │
│  ┌───────────┐  ┌────────────┐  │
│  │ Analyzer  │  │ Anomaly    │  │
│  │ (KPI,     │  │ Detector   │  │
│  │  profit,  │  │ (Isolation │  │
│  │  margin,  │  │  Forest)   │  │
│  │  burn     │  └────────────┘  │
│  │  rate,    │  ┌────────────┐  │
│  │  runway)  │  │ Forecast   │  │
│  └───────────┘  │ (MA ±1σ)   │  │
│  ┌───────────┐  └────────────┘  │
│  │ Health    │  ┌────────────┐  │
│  │ Score     │  │ Insights   │  │
│  │ (3 comp.) │  │ (GigaChat) │  │
│  └───────────┘  └────────────┘  │
└───────────────┬─────────────────┘
                ▼
┌─────────────────────────────────┐
│  Alpine.js SPA + Chart.js       │
│  Dashboard · Analytics · Agent  │
└─────────────────────────────────┘
```

---

## Технологии

| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| Backend | FastAPI | REST API, сессии, Jinja2 |
| Frontend | Alpine.js + Chart.js 4 | SPA, графики, тема |
| Данные | Pandas | Обработка CSV, агрегации |
| ML | scikit-learn | Isolation Forest (аномалии) |
| LLM | GigaChat API | Бизнес-инсайты, чат |
| Деплой | Docker | Контейнеризация |

---

## Быстрый старт

### Docker

```bash
git clone https://github.com/<your-username>/ai-financial-copilot.git
cd ai-financial-copilot

echo "GIGACHAT_CREDENTIALS=ваш_токен" > .env

docker-compose up --build
```

Приложение: **http://localhost:8000**

### Локальный запуск

```bash
pip install -r requirements.txt

# Сгенерировать демо-данные (ИП мармелад, 4 месяца)
python data/generate_business_demo.py

export GIGACHAT_CREDENTIALS=ваш_токен

uvicorn main:app --reload --port 8000
```

### Получение токена GigaChat

1. Зарегистрироваться на [developers.sber.ru](https://developers.sber.ru/)
2. Создать проект → получить Client ID + Client Secret
3. Сформировать credentials (base64 от `client_id:client_secret`)
4. Указать в `.env`

> Без GigaChat приложение работает — показываются кэшированные инсайты.

---

## Формат данных

CSV с 5 обязательными колонками:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `date` | дата | Дата транзакции (`2024-11-05`) |
| `amount` | число | Сумма (всегда положительная) |
| `type` | строка | `income` или `expense` |
| `category` | строка | Категория операции |
| `description` | строка | Описание транзакции |

Пример:
```csv
date,amount,type,category,description
2024-11-01,45000,income,маркетплейс,Ozon — продажи мармелада
2024-11-02,12000,expense,зарплата,Зарплата упаковщику
2024-11-03,3500,expense,реклама,Яндекс Директ — кампания
```

Можно загружать несколько файлов (по месяцам) — система объединит автоматически.

---

## API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/init` | Инициализация сессии с демо-данными |
| POST | `/api/upload` | Загрузка CSV |
| GET | `/api/analytics/{session_id}` | Аналитика по выбранному месяцу |
| GET | `/api/metrics/{session_id}` | Общие бизнес-метрики |
| GET | `/api/forecast/{session_id}` | Прогноз на 30/60 дней |
| POST | `/api/insights` | Генерация AI-инсайтов (GigaChat) |
| POST | `/api/chat` | Чат с AI-агентом |
| GET | `/api/agent` | Возможности AI-агента |
| GET | `/health` | Healthcheck |

---

## Структура проекта

```
ai-financial-copilot/
├── main.py                          # FastAPI entrypoint
├── api/
│   └── routes.py                    # REST API endpoints
├── core/
│   ├── data_loader.py               # Парсинг CSV, валидация, производные признаки
│   ├── analyzer.py                  # Бизнес-метрики: profit, margin, burn rate, runway
│   ├── anomaly_detector.py          # Isolation Forest
│   ├── health_score.py              # Health Score (3 компоненты)
│   ├── forecast.py                  # Прогноз (Moving Average ±1σ)
│   └── insights.py                  # GigaChat pipeline + fallback
├── templates/
│   └── index.html                   # Alpine.js SPA (3 views)
├── static/
│   ├── css/style.css                # Dark/light themes, glassmorphism
│   └── js/
│       ├── app.js                   # Alpine.js компонент
│       └── charts.js                # Chart.js графики
├── data/
│   ├── generate_business_demo.py    # Генератор демо-данных (ИП мармелад)
│   └── cached_insights.json         # Fallback инсайты
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Описание модулей

### core/data_loader.py
Загрузка CSV с валидацией 5 обязательных колонок (`date`, `amount`, `type`, `category`, `description`). Проверка type ∈ {income, expense}. Добавление производных: `abs_amount`, `month`, `month_year`, `day_of_week`, `is_weekend`.

### core/analyzer.py
Бизнес-аналитика: total_income, total_expenses, profit, profit_margin, burn_rate, runway, revenue_by_channel, расходы по категориям с процентами, MoM-изменения, топ-транзакции, weekend_ratio.

### core/anomaly_detector.py
Isolation Forest (scikit-learn, contamination=0.05). Признаки: абсолютная сумма, отношение к среднему по категории, z-score, день недели. Обучается на всём датасете.

### core/health_score.py
Комплексная оценка (0–100):
- **Profit Margin** (35%) — маржинальность бизнеса (≥20% → 100)
- **Revenue Stability** (30%) — стабильность выручки (CV месячного дохода)
- **Cost Structure** (35%) — доля фиксированных расходов (зарплата + коммунальные)

### core/forecast.py
Прогноз расходов через скользящее среднее за 30 дней с доверительным интервалом (±1σ).

### core/insights.py
GigaChat API с бизнес-промптом (выручка, расходы, прибыль, маржа, burn rate, runway, каналы). Парсинг структурированного ответа. Fallback на `cached_insights.json`.

---

## Roadmap

### v1.0 — B2C Personal Finance ✅
- [x] CSV загрузка и категоризация
- [x] Streamlit дашборд
- [x] Anomaly detection + Health Score
- [x] AI-инсайты (GigaChat)

### v2.0 — B2B Financial Analytics ✅
- [x] Миграция на FastAPI + Alpine.js
- [x] Бизнес-метрики: profit, margin, burn rate, runway
- [x] Revenue by channel
- [x] Dark/light theme с glassmorphism
- [x] 3 views: Dashboard, Analytics, AI Agent
- [x] Business Health Score (новые компоненты)
- [x] Чат с контекстом бизнес-метрик

### v2.1 — Расширение
- [ ] RAG-агент с полной базой знаний
- [ ] Подключение банковских API
- [ ] Экспорт отчётов (PDF)
- [ ] Мультиязычность

### v3.0 — Масштабирование
- [ ] Многопользовательский режим + авторизация
- [ ] PostgreSQL для хранения данных
- [ ] White-label для банков и бухгалтерских сервисов
- [ ] Интеграция с 1С и МойСклад

---

## Команда

| Участник | Роль | Зона ответственности |
|----------|------|----------------------|
| Ягфаров Рустам | ML-специалист | Core-модули, ML pipeline, GigaChat интеграция |
| Ноговицын Михаил | Менеджер | UI/UX, архитектура, Docker, документация |

---

## Лицензия

MIT License

---

<p align="center">
  <b>AI Financial Copilot</b> — финансовая аналитика для бизнеса
</p>
