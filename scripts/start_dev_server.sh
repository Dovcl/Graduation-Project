#!/usr/bin/env bash
# 로컬 개발용: 코드 변경 시 자동 재시작 (--reload)
# 사용법: ./scripts/start_dev_server.sh  또는  bash scripts/start_dev_server.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../backend" && pwd)"
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
  echo "❌ venv 없음: $BACKEND_DIR/venv"
  exit 1
fi

echo "📂 작업 디렉토리: $BACKEND_DIR"
echo "🔄 변경 시 자동 재시작 (--reload) 사용"
echo "🌐 http://localhost:8000"
echo ""

source venv/bin/activate
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
