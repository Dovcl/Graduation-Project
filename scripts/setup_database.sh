#!/bin/bash

# PostgreSQL 데이터베이스 및 확장 설정 스크립트

set -e

POSTGRES_VERSION="18"
PSQL="/Library/PostgreSQL/${POSTGRES_VERSION}/bin/psql"
DB_NAME="rag_chatbot_db"
DB_USER="postgres"
DB_PASSWORD="!kdh032500"

echo "=========================================="
echo "PostgreSQL 데이터베이스 설정"
echo "=========================================="

# PGPASSWORD 환경 변수 설정
export PGPASSWORD="$DB_PASSWORD"

echo "1. 데이터베이스 존재 여부 확인..."
DB_EXISTS=$($PSQL -U $DB_USER -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null || echo "")

if [ "$DB_EXISTS" = "1" ]; then
    echo "   ✓ 데이터베이스 '$DB_NAME'가 이미 존재합니다."
else
    echo "2. 데이터베이스 생성 중..."
    $PSQL -U $DB_USER -c "CREATE DATABASE $DB_NAME;"
    echo "   ✓ 데이터베이스 '$DB_NAME' 생성 완료!"
fi

echo ""
echo "3. pgvector 확장 설치 중..."
$PSQL -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo "   ✓ pgvector 확장 설치 완료!"

echo ""
echo "4. 확장 확인..."
$PSQL -U $DB_USER -d $DB_NAME -c "\dx" | grep vector || echo "   (확장 목록 확인 중...)"

echo ""
echo "=========================================="
echo "✓ 데이터베이스 설정 완료!"
echo "=========================================="
echo "데이터베이스: $DB_NAME"
echo "연결 문자열: postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
echo ""

# PGPASSWORD 제거
unset PGPASSWORD

