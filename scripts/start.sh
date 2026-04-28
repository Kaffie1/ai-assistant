#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-cli}"
ENV_NAME="${ENV_NAME:-langchain}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

run_cli() {
  echo "启动 CLI 模式（conda env: ${ENV_NAME}）"
  conda run --no-capture-output -n "${ENV_NAME}" python entrypoints/chat_cli.py
}

run_web() {
  echo "启动 Web 模式（conda env: ${ENV_NAME}, host: ${HOST}, port: ${PORT}）"
  conda run --no-capture-output -n "${ENV_NAME}" uvicorn entrypoints.web_app:app --host "${HOST}" --port "${PORT}"
}

print_help() {
  cat <<EOF
用法:
  bash scripts/start.sh [cli|web]

可选环境变量:
  ENV_NAME   conda 环境名，默认 langchain
  HOST       Web 绑定地址，默认 0.0.0.0
  PORT       Web 端口，默认 8000

示例:
  bash scripts/start.sh
  bash scripts/start.sh cli
  bash scripts/start.sh web
  HOST=127.0.0.1 PORT=9000 bash scripts/start.sh web
EOF
}

case "${MODE}" in
  cli)
    run_cli
    ;;
  web)
    run_web
    ;;
  -h|--help|help)
    print_help
    ;;
  *)
    echo "未知模式: ${MODE}" >&2
    print_help
    exit 1
    ;;
esac
