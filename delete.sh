#!/usr/bin/env bash
# Видалити сервіс, секрет і образи, щоб нічого не списувалось.
REGION=${REGION:-europe-west3}
gcloud run services delete konspekt --region "$REGION" --quiet
gcloud secrets delete anthropic-api-key --quiet
gcloud artifacts repositories delete cloud-run-source-deploy --location "$REGION" --quiet 2>/dev/null || true
