# 🎓 RAG Assistant — чат-бот-помощник для сайта

Универсальный RAG-бот, который отвечает на вопросы пользователей на основе
базы знаний (документы, страницы сайта, PDF). Работает локально, без
обязательных платежей за облачные API.

## Возможности

- 🤖 **Гибридный поиск** — векторный (pgvector + HNSW) + лексический
  (PostgreSQL FTS) + Reciprocal Rank Fusion.
- 🧠 **Любая LLM** — OpenAI, OpenRouter, Groq, vLLM, **Ollama** (локально,
  бесплатно).
- 📚 **Индексация из разных источников** — PDF, HTML, текстовые файлы.
- 🎯 **Два маршрута ответов**:
  - **Intent** — быстрый, детерминированный (по кнопкам, без LLM).
  - **RAG** — свободный текст, с гибридным поиском и LLM.
- 📎 **Отправка файлов** — бот прикрепляет PDF к ответу (`/api/v1/files/{id}`).
- 🔘 **Quick replies** — кнопки с популярными вопросами.
- 💾 **Память диалога** — `session_id` сохраняется в `localStorage`.
- 🌐 **Веб-виджет** — встраивается на любой сайт одной строкой `<script>`.
- 🤖 **Telegram-бот** — тот же API, другой интерфейс (в разработке).

## Архитектура

```
┌─────────────┐     ┌─────────────┐
│ Web-виджет  │     │ Telegram    │
│ (iframe)    │     │ (aiogram)   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │ HTTP
                 ▼
        ┌────────────────┐
        │  FastAPI       │
        │  /api/v1/chat  │
        └───────┬────────┘
                │
        ┌───────▼────────┐
        │  ChatService   │
        │ ┌────────────┐ │
        │ │  Intent    │ │  ← детерминированный маршрут
        │ └────────────┘ │
        │ ┌────────────┐ │
        │ │   RAG      │ │  ← гибридный поиск + LLM
        │ └────────────┘ │
        └───────┬────────┘
                │
       ┌────────┴─────────┐
       ▼                  ▼
┌─────────────┐    ┌─────────────┐
│ PostgreSQL  │    │ LLM         │
│ + pgvector  │    │ (Ollama /   │
│ + FTS       │    │  OpenAI)    │
└─────────────┘    └─────────────┘
```

## Технологии

| Слой | Технология |
|---|---|
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2 (async) |
| БД | PostgreSQL 16 + `pgvector` + встроенный FTS |
| Миграции | Alembic |
| LLM | Ollama (по умолчанию), OpenAI / OpenRouter / vLLM |
| Embeddings | Ollama (`nomic-embed-text`, 768) / OpenAI (`text-embedding-3-small`, 1536) |
| Интерфейсы | Vanilla JS (виджет), aiogram 3 (Telegram) |
| Хранилище файлов | Локальная ФС (легко переехать на S3/MinIO) |

## Требования

- **Python 3.11+**
- **Docker Desktop** (для PostgreSQL)
- **Ollama** — если хотите работать без облачных API-ключей
  ([ollama.com/download](https://ollama.com/download))

## 🚀 Быстрый старт

### 1. Клонирование и окружение

```powershell
git clone <url> RAG
cd RAG

python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
```

### 2. Модели для Ollama

```powershell
ollama pull llama3.2:3b          # генеративная модель (~2 GB)
ollama pull nomic-embed-text     # эмбеддинги, 768 измерений (~274 MB)
```

Проверка:

```powershell
curl http://localhost:11434/api/tags
```

### 3. PostgreSQL с pgvector

```yaml
# docker-compose.yml (создайте, если нет)
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: rag
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

```powershell
docker compose up -d db
docker ps --filter "name=rag-db"
# STATUS: Up X seconds (healthy)
```

> ⚠️ **Если на порту 5432 уже висит другой PostgreSQL** (локальная установка),
> поменяйте маппинг на `"5433:5432"` и поправьте `DATABASE_URL` в `.env`.

### 4. Конфигурация — `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

**Минимальный `.env` для работы с Ollama:**

```bash
# --- Database ---
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rag

# --- LLM (Ollama, OpenAI-совместимый) ---
LLM_PROVIDER=openai
LLM_MODEL=llama3.2:3b
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=800

# --- Embeddings ---
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768

# --- Chunking ---
CHUNK_SIZE=800
CHUNK_OVERLAP=120

# --- Retrieval ---
TOP_K_VECTOR=20
TOP_K_BM25=20
TOP_K_FINAL=6
RRF_K=60
FTS_LANGUAGE=russian

# --- Storage ---
RAW_DIR=data/raw
STORAGE_DIR=data/storage

# --- HTTP ---
CORS_ORIGINS=["http://localhost:8000","http://localhost:3000","http://localhost:5173"]
ADMIN_API_KEY=dev-secret
```

> ⚠️ **`EMBEDDING_DIM` должен совпадать** с колонкой `embedding` в БД.
> `nomic-embed-text` = 768, `text-embedding-3-small` = 1536. Если меняете
> модель эмбеддингов — нужна новая миграция `ALTER COLUMN`.

### 5. Миграции

```powershell
alembic upgrade head
```

Проверка:

```powershell
docker exec -it rag-db-1 psql -U postgres -d rag -c "\dt"
# alembic_version, chunks, conversations, documents, messages
```

### 6. Загрузка демо-данных

```powershell
python -m scripts.seed_demo
```

Ожидаемо:

```
{'document_id': 1, 'status': 'created', 'chunks_created': 3}
{'document_id': 2, 'status': 'created', 'chunks_created': 2}
```

### 7. Запуск

```powershell
uvicorn src.core.main:app --reload
```

Откройте **http://localhost:8000/docs** — Swagger UI.

### 8. Первый запрос

```powershell
curl.exe -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"Когда консультация по матанализу?\"}"
```

Ожидаемый ответ:

```json
{
  "session_id": "...",
  "message_id": 2,
  "answer": "Консультация по математическому анализу — в среду, 15:00, ауд. 312.",
  "sources": [{"chunk_id": 1, "document_id": 1, "title": "Расписание матана", ...}],
  "usage": {"model": "llama3.2:3b", "latency_ms": 842}
}
```

### 9. Веб-виджет

**Вариант A — через FastAPI (проще для dev):**

Виджет лежит в `widget/` в корне проекта, `main.py` раздаёт его через `StaticFiles`:

```python
# src/core/main.py (в конце файла)
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_widget_dir = Path("widget")
if _widget_dir.exists():
    app.mount("/widget", StaticFiles(directory=_widget_dir, html=True), name="widget")
```

Создайте `test.html`:

```html
<!DOCTYPE html>
<html>
<body>
    <h1>Сайт университета</h1>
    <script src="http://localhost:8000/widget/embed.js"></script>
</body>
</html>
```

Откройте `test.html` — в правом нижнем углу появится кнопка 💬.

**Вариант B — отдельный сервер (для теста):**

```powershell
cd widget
python -m http.server 3000
```

И `<script src="http://localhost:3000/embed.js">`.

## 📁 Структура проекта

```
RAG/
├── alembic.ini
├── docker-compose.yml
├── .env.example
├── requirements.txt
│
├── data/
│   ├── raw/                    # inbox для PDF (до индексации)
│   └── storage/                # durable, файлы для отдачи
│
├── migrations/                 # Alembic
│   └── versions/
│
├── scripts/                    # CLI-операции
│   ├── seed_demo.py
│   ├── ingest_pdf.py
│   ├── ingest_urls.py
│   └── cleanup_orphans.py
│
├── src/
│   ├── core/
│   │   ├── main.py             # FastAPI app, CORS, StaticFiles
│   │   ├── config.py           # Pydantic Settings
│   │   ├── api/                # роуты и схемы
│   │   │   ├── schemas.py
│   │   │   └── routes/
│   │   ├── db/                 # SQLAlchemy
│   │   │   ├── session.py
│   │   │   └── models.py
│   │   ├── llm/                # абстракция LLM
│   │   ├── rag/                # гибридный поиск, индексация
│   │   ├── services/           # ChatService, intents, history
│   │   └── storage/            # StorageBackend (local / s3)
│   │
│   ├── interfaces/
│   │   ├── telegram_bot/
│   │   └── web_widget/         # (или /widget в корне)
│   │
│   └── shared/
│
└── widget/                     # статика веб-виджета
    ├── embed.js
    ├── index.html
    ├── app.js
    └── style.css
```

## 🔌 API

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/health` | Liveness-проба |
| `GET` | `/ready` | Readiness (БД + LLM) |
| `POST` | `/api/v1/chat` | Основной эндпоинт (message или intent) |
| `GET` | `/api/v1/files/{id}` | Скачивание вложений |
| `POST` | `/api/v1/admin/ingest/url` | Индексация одной страницы |
| `GET` | `/docs` | Swagger UI |

### `POST /api/v1/chat` — запрос

```json
{
  "message": "когда консультация?",
  "session_id": "8f3b...",
  "channel": "web"
}
```

**Или** (для кнопок):

```json
{
  "intent": "show_schedule",
  "session_id": "8f3b...",
  "channel": "web"
}
```

### `POST /api/v1/chat` — ответ

```json
{
  "session_id": "8f3b...",
  "message_id": 5,
  "answer": "Консультация в среду, 15:00",
  "sources": [{"chunk_id": 1, "title": "...", "score": 0.03}],
  "attachments": [{"document_id": 1, "filename": "schedule.pdf", "url": "/api/v1/files/1"}],
  "quick_replies": [{"label": "🎓 Приёмная комиссия", "intent": "admission"}],
  "usage": {"model": "llama3.2:3b", "latency_ms": 842}
}
```

## 📚 Загрузка знаний

### Демо-данные

```powershell
python -m scripts.seed_demo
```

### PDF из `data/raw/`

```powershell
# Положите PDF в inbox
Copy-Item C:\path\to\schedule.pdf data\raw\

# Проиндексировать
python -m scripts.ingest_pdf data\raw\schedule.pdf

# Или все файлы
python -m scripts.ingest_pdf --all
```

После успешной индексации файл **переезжает** в `data/storage/documents/{id}/`,
из `data/raw/` удаляется. Ноль дублирования.

### Страница сайта

```powershell
curl.exe -X POST http://localhost:8000/api/v1/admin/ingest/url `
  -H "Content-Type: application/json" `
  -H "X-Admin-Key: dev-secret" `
  -d "{\"url\":\"https://university.ru/schedule\",\"source_type\":\"schedule\"}"
```

## 🧪 Полезные команды

```powershell
# API
uvicorn src.core.main:app --reload
uvicorn src.core.main:app --reload --port 8001
uvicorn src.core.main:app --host 0.0.0.0 --port 8000

# Docker
docker compose up -d db
docker compose down
docker compose down -v                    # ⚠️ удалит данные БД
docker compose logs -f db

# Alembic
alembic upgrade head                      # применить миграции
alembic downgrade -1                      # откатить последнюю
alembic current                           # где мы
alembic revision --autogenerate -m "..."  # новая миграция

# БД
docker exec -it rag-db-1 psql -U postgres -d rag
docker exec -it rag-db-1 psql -U postgres -d rag -c "\dt"
docker exec -it rag-db-1 psql -U postgres -d rag -c "SELECT count(*) FROM chunks;"

# Тест preflight CORS
curl.exe -i -X OPTIONS http://localhost:8000/api/v1/chat `
  -H "Origin: http://localhost:8000" `
  -H "Access-Control-Request-Method: POST"
```

## 🛠️ Troubleshooting

### `relation "documents" does not exist`

Миграции не применены.

```powershell
alembic upgrade head
docker exec -it rag-db-1 psql -U postgres -d rag -c "\dt"
```

Если `alembic current` пуст, но миграции «есть» — проверьте `migrations/env.py`:
там должны быть `import src.core.db.models` и `target_metadata = Base.metadata`.

### `NameError: name 'pgvector' is not defined`

Alembic не добавил `import pgvector` в файл миграции. Добавьте вручную
в начало `migrations/versions/*.py`:

```python
import pgvector
```

Или настройте шаблон `migrations/script.py.mako`, чтобы импорт добавлялся
автоматически.

### `Connection refused` при `alembic upgrade`

Postgres не слушает порт. Проверьте:

```powershell
docker ps --filter "name=rag-db"        # контейнер запущен?
docker port rag-db-1                    # на каком порту?
Get-NetTCPConnection -LocalPort 5432    # порт не занят другим Postgres?
```

Если `docker port` показывает `5433` — исправьте `DATABASE_URL` в `.env`.
Если порт 5432 занят локальным Postgres — либо остановите его
(`services.msc` → PostgreSQL → Stop), либо переключите Docker на 5433.

### `422 Unprocessable Entity` на `POST /chat`

Поле `message` обязательно, а вы прислали только `intent` (или наоборот).
Откройте DevTools → Network → кликните на запрос → **Response** —
там указано, какое именно поле не прошло валидацию.

Проверьте `src/core/api/schemas.py` — `ChatRequest.message` должен быть
`str | None = None`, а не `Field(...)`.

### `400 Bad Request` на `OPTIONS /api/v1/chat`

CORS не пропускает preflight. Проверьте:

```powershell
python -c "from src.core.config import settings; print(settings.cors_origins)"
```

Origin виджета должен быть в этом списке. `localhost` и `127.0.0.1` —
**разные** origin'ы, добавляйте оба.

### `Invalid HTTP request received`

Uvicorn получает HTTPS вместо HTTP. Проверьте, что все URL в `app.js`
и `test.html` начинаются с `http://`.

### `404` на `/embed.js`

Виджет не смонтирован. Добавьте в конец `src/core/main.py`:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_widget_dir = Path("widget")
if _widget_dir.exists():
    app.mount("/widget", StaticFiles(directory=_widget_dir, html=True), name="widget")
```

И убедитесь, что `embed.js` лежит в `widget/` в корне проекта.

### Медленные ответы

`llama3.2:3b` на CPU выдаёт ~5–10 токенов/с. Ответ на 100 токенов — 10–20 секунд.
Для ускорения: GPU (`ollama` использует его автоматически, если есть),
или `qwen2.5:0.5b` (быстрее, но глупее), или облачная LLM (OpenRouter / Groq —
бесплатные ключи).

## 🗺️ Roadmap

- [x] Гибридный поиск (vector + BM25 + RRF)
- [x] Абстракция LLM (Ollama / OpenAI)
- [x] Память диалога (`session_id`)
- [x] Веб-виджет
- [x] Прикрепление файлов (`/api/v1/files/{id}`)
- [x] Intent-маршрут (кнопки)
- [ ] Telegram-бот
- [ ] OCR для сканированных PDF (Tesseract + коррекция поворота)
- [ ] Загрузка PDF через админку (вместо `scripts/ingest_pdf`)
- [ ] Streaming ответов (SSE)
- [ ] Кэширование частых вопросов (Redis)
- [ ] Оценка качества (eval-набор, RAGAS)
- [ ] S3/MinIO для хранения файлов
- [ ] Docker-образ для продакшена

## 📄 Лицензия

MIT (или ваша).
```

---

## 🎯 Что важно в этом README

1. **Отражает реальный стек** — Ollama, `nomic-embed-text` (768), `llama3.2:3b` — то, что у вас фактически работает.
2. **Troubleshooting собран из наших грабель** — `pgvector is not defined`, `Connection refused`, 422 на кнопки, 400 на OPTIONS. Это те проблемы, которые **точно** возникнут у следующего, кто развернёт проект.
3. **Два пути для виджета** — через `StaticFiles` (проще) и через `http.server` (для теста).
4. **`.env` пример** — рабочий, скопировал-и-запустил.
5. **Структура проекта** — совпадает с тем, что вы построили.
6. **Roadmap** — показывает, что уже сделано и куда двигаться.

**Параллельно стоит создать `.env.example`** — тот же `.env`, но без реальных ключей (для Ollama там вообще ключ `ollama`, так что он безопасен).

И **`.gitignore`** — обязательно:

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/

# Окружение
.env
.env.local

# Данные
data/raw/*
!data/raw/.gitkeep
data/storage/*
!data/storage/.gitkeep

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Логи
*.log
```