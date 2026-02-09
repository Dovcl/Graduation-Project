#!/bin/bash

# 배포 스크립트
# 사용법: ./deploy.sh

set -e  # 오류 발생 시 중단

echo "🚀 배포 시작..."

# 1. Git 최신 버전 가져오기
echo "📥 Git 최신 버전 가져오기..."
git pull origin feature/visualization

# 2. 데이터베이스 시작
echo "🗄️ 데이터베이스 시작..."
docker-compose up -d postgres

# 3. 백엔드 의존성 확인
echo "📦 백엔드 의존성 확인..."
cd backend
if [ ! -d "venv" ]; then
    echo "가상환경 생성..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

# 4. 데이터베이스 마이그레이션 (필요시)
echo "🔄 데이터베이스 마이그레이션..."
# alembic upgrade head  # 필요시 주석 해제

# 5. 기존 서버 종료
echo "🛑 기존 서버 종료..."
pkill -f "uvicorn app.main:app" || true

# 6. 백엔드 서버 시작
echo "▶️ 백엔드 서버 시작..."
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
echo "백엔드 서버 PID: $!"

cd ..

# 7. 프론트엔드 서버 시작 (선택사항)
# echo "▶️ 프론트엔드 서버 시작..."
# cd frontend
# pkill -f "http.server 8080" || true
# nohup python3 -m http.server 8080 > ../frontend.log 2>&1 &
# cd ..

echo "✅ 배포 완료!"
echo ""
echo "백엔드 API: http://$(hostname -I | awk '{print $1}'):8000"
echo "프론트엔드: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "로그 확인:"
echo "  - 백엔드: tail -f backend/server.log"
echo "  - 데이터베이스: docker-compose logs postgres"

