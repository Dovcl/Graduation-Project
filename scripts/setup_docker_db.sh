#!/bin/bash

# Docker PostgreSQL + pgvector 설정 스크립트

set -e

echo "=========================================="
echo "Docker PostgreSQL + pgvector 설정"
echo "=========================================="

# 1. Docker Compose로 PostgreSQL 시작
echo "1. Docker Compose로 PostgreSQL 시작 중..."
cd "$(dirname "$0")/.."
docker-compose up -d postgres

# 컨테이너가 준비될 때까지 대기
echo "2. PostgreSQL 준비 대기 중..."
sleep 5

# 헬스 체크
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "✓ PostgreSQL 준비 완료!"
        break
    fi
    attempt=$((attempt + 1))
    echo "  대기 중... ($attempt/$max_attempts)"
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo "✗ PostgreSQL 시작 실패"
    exit 1
fi

# 3. pgvector 확장 설치
echo "3. pgvector 확장 설치 중..."
docker-compose exec -T postgres psql -U postgres -d rag_chatbot_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 4. 확인
echo "4. 설치 확인 중..."
docker-compose exec -T postgres psql -U postgres -d rag_chatbot_db -c "\dx" | grep vector

echo ""
echo "=========================================="
echo "✓ Docker PostgreSQL + pgvector 설정 완료!"
echo "=========================================="
echo ""
echo "연결 정보:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: rag_chatbot_db"
echo "  User: postgres"
echo "  Password: !kdh032500"
echo ""
echo "Docker 명령어:"
echo "  시작: docker-compose up -d"
echo "  중지: docker-compose down"
echo "  로그: docker-compose logs -f postgres"
echo ""

