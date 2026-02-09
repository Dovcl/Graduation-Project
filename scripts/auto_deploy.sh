#!/bin/bash

# 자동 배포 스크립트 (서버에서 실행)
# GitHub에 푸시하면 자동으로 이 스크립트가 실행되어 배포됨

set -e

PROJECT_DIR="/path/to/rag-chatbot"  # 실제 프로젝트 경로로 변경 필요
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_FILE="$PROJECT_DIR/deploy.log"

echo "[$(date)] 🚀 자동 배포 시작..." >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 1. Git 최신 버전 가져오기
echo "[$(date)] 📥 Git pull..." >> "$LOG_FILE"
git pull origin main 2>&1 | tee -a "$LOG_FILE"

# 2. 데이터베이스 확인
echo "[$(date)] 🗄️ 데이터베이스 확인..." >> "$LOG_FILE"
cd "$PROJECT_DIR"
docker-compose up -d postgres 2>&1 | tee -a "$LOG_FILE"

# 3. 백엔드 의존성 업데이트
echo "[$(date)] 📦 백엔드 의존성 업데이트..." >> "$LOG_FILE"
cd "$BACKEND_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt --quiet 2>&1 | tee -a "$LOG_FILE"

# 4. 기존 서버 종료
echo "[$(date)] 🛑 기존 서버 종료..." >> "$LOG_FILE"
pkill -f "uvicorn app.main:app" || true
sleep 2

# 5. 서버 재시작
echo "[$(date)] ▶️ 서버 재시작..." >> "$LOG_FILE"
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$BACKEND_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "[$(date)] ✅ 서버 시작됨 (PID: $SERVER_PID)" >> "$LOG_FILE"

# 6. 서버 상태 확인
sleep 3
if ps -p $SERVER_PID > /dev/null; then
    echo "[$(date)] ✅ 배포 성공!" >> "$LOG_FILE"
    echo "✅ 배포 완료! 서버 PID: $SERVER_PID"
else
    echo "[$(date)] ❌ 배포 실패 - 서버가 시작되지 않음" >> "$LOG_FILE"
    echo "❌ 배포 실패. 로그 확인: $BACKEND_DIR/server.log"
    exit 1
fi

