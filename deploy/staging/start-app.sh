#!/bin/sh
set -eu

: "${BIOINFO_API_KEY_FILE:=/run/secrets/bioinfo_api_key}"
: "${BIOINFO_INPUT_ROOT:?BIOINFO_INPUT_ROOT is required}"
: "${BIOINFO_OUTPUT_ROOT:?BIOINFO_OUTPUT_ROOT is required}"
: "${BIOINFO_TASK_STORE_PATH:?BIOINFO_TASK_STORE_PATH is required}"

if [ ! -r "$BIOINFO_API_KEY_FILE" ]; then
  echo "Staging API key file is unavailable" >&2
  exit 1
fi

BIOINFO_API_KEY="$(tr -d '\r\n' < "$BIOINFO_API_KEY_FILE")"
if [ -z "$BIOINFO_API_KEY" ]; then
  echo "Staging API key is unavailable" >&2
  exit 1
fi
export BIOINFO_API_KEY
unset BIOINFO_API_KEY_FILE

mkdir -p "$(dirname "$BIOINFO_TASK_STORE_PATH")" "$BIOINFO_OUTPUT_ROOT"

exec python -m uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --no-proxy-headers \
  --log-level "${BIOINFO_LOG_LEVEL:-info}" \
  --timeout-graceful-shutdown 25
