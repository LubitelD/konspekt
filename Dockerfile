FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Cloud Run передає порт у змінній PORT (за замовчуванням 8080)
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
