#!/usr/bin/env bash
# Розгортання «Конспектувача» в Google Cloud Run. Запуск з кореня репозиторію в Cloud Shell.
#   ./deploy.sh                       — перше розгортання (попросить API-ключ Anthropic)
#   ACCESS_CODE=1234 ./deploy.sh      — з кодом доступу, щоб чужі не витрачали твої кредити
set -euo pipefail

PROJECT=${PROJECT:-$(gcloud config get-value project 2>/dev/null)}
REGION=${REGION:-europe-west3}
SERVICE=${SERVICE:-konspekt}
SECRET=anthropic-api-key
[ -n "$PROJECT" ] || { echo "Задай проєкт: gcloud config set project <PROJECT_ID>"; exit 1; }

# 1. Увімкнути потрібні API Google Cloud
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com --project "$PROJECT"

# 2. Покласти ключ Claude API в Secret Manager (лише якщо секрету ще немає)
if ! gcloud secrets describe "$SECRET" --project "$PROJECT" >/dev/null 2>&1; then
  read -rsp "Встав API-ключ з console.anthropic.com (sk-ant-...): " KEY; echo
  printf "%s" "$KEY" | gcloud secrets create "$SECRET" --data-file=- --project "$PROJECT"
fi

# 3. Дати сервісному акаунту Cloud Run право читати секрет
NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding "$SECRET" --project "$PROJECT" \
  --member "serviceAccount:${NUM}-compute@developer.gserviceaccount.com" \
  --role roles/secretmanager.secretAccessor >/dev/null

# 4. Зібрати контейнер (Cloud Build) і розгорнути (Cloud Run)
gcloud run deploy "$SERVICE" --source . --region "$REGION" --project "$PROJECT" \
  --allow-unauthenticated --memory 512Mi --max-instances 2 \
  --set-secrets "ANTHROPIC_API_KEY=${SECRET}:latest" \
  --set-env-vars "ACCESS_CODE=${ACCESS_CODE:-}"

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format='value(status.url)')
echo; echo "Готово: $URL"
curl -s "$URL/api/health"; echo
