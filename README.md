# Конспектувач — AI-сервіс конспектів лекцій на Claude API + Google Cloud Run

Вебсервіс: вставляєш текст лекції (або завантажуєш `.txt`), а Claude складає структурований конспект:
назву теми, стислий виклад, головні тези, терміни з визначеннями та питання для самоперевірки.

## Архітектура

```
Браузер ──HTTPS──▶ Cloud Run (FastAPI, main.py) ──HTTPS──▶ Claude Messages API (claude-haiku-5-5)
                         │
                         └── ANTHROPIC_API_KEY ◀── Secret Manager
Cloud Build збирає Docker-образ → Artifact Registry → Cloud Run
```

| Компонент | Роль |
|---|---|
| `static/index.html` | фронтенд: форма, виклик `POST /api/notes`, відображення конспекту |
| `main.py` | бекенд FastAPI: валідація, виклик Claude API з tool use, повернення JSON |
| Claude Messages API | модель `claude-haiku-5-5`; інструмент `save_notes` з JSON-схемою гарантує структуровану відповідь |
| Secret Manager | зберігає API-ключ Anthropic, Cloud Run отримує його як змінну середовища |
| Cloud Build + Artifact Registry | збирають і зберігають контейнер з `Dockerfile` |
| Cloud Run | запускає контейнер, масштабує від 0 до 2 інстансів, дає HTTPS-адресу |

## API сервісу

| Метод | Шлях | Опис |
|---|---|---|
| GET | `/` | вебсторінка |
| GET | `/api/health` | стан сервісу, модель, чи налаштовано ключ |
| POST | `/api/notes` | `{"text": "..."}` → `{"notes": {...}, "meta": {model, input_tokens, output_tokens, seconds}}` |

Якщо задано `ACCESS_CODE`, запит має містити заголовок `X-Access-Code`.

## Розгортання (Cloud Shell)

1. Створи API-ключ: console.anthropic.com → API Keys → Create Key.
2. У Cloud Shell:
```bash
git clone https://github.com/<логін>/konspekt.git && cd konspekt
gcloud config set project <PROJECT_ID>
ACCESS_CODE=1234 ./deploy.sh      # попросить вставити ключ; наприкінці надрукує URL
```
3. Відкрий URL у браузері, введи код доступу `1234`, натисни «Приклад» → «Скласти конспект».

Видалити все: `./delete.sh`.

## Локальний запуск

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload --port 8080    # http://localhost:8080
python3 tests/test_app.py                # тест без мережі (Claude підмінено заглушкою)
```
