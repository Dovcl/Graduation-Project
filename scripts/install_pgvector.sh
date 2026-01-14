#!/bin/bash

# pgvector 확장 설치 스크립트

set -e

POSTGRES_VERSION="18"
POSTGRES_HOME="/Library/PostgreSQL/${POSTGRES_VERSION}"
PGVECTOR_HOME="/opt/homebrew/Cellar/pgvector/0.8.1"

echo "=========================================="
echo "pgvector 확장 설치"
echo "=========================================="

# 1. extension 파일 복사
echo "1. extension 파일 복사 중..."
sudo cp -r ${PGVECTOR_HOME}/share/postgresql@${POSTGRES_VERSION}/extension/* ${POSTGRES_HOME}/share/postgresql/extension/

# 2. 라이브러리 파일 복사
echo "2. 라이브러리 파일 복사 중..."
sudo cp ${PGVECTOR_HOME}/lib/postgresql@${POSTGRES_VERSION}/vector.dylib ${POSTGRES_HOME}/lib/

# 3. 권한 설정
echo "3. 권한 설정 중..."
sudo chown postgres:daemon ${POSTGRES_HOME}/share/postgresql/extension/vector*
sudo chown postgres:daemon ${POSTGRES_HOME}/lib/vector.dylib

# 4. PostgreSQL 재시작
echo "4. PostgreSQL 재시작 중..."
sudo launchctl unload /Library/LaunchDaemons/com.edb.postgresql-${POSTGRES_VERSION}.plist
sleep 2
sudo launchctl load /Library/LaunchDaemons/com.edb.postgresql-${POSTGRES_VERSION}.plist
sleep 3

# 5. 확장 설치
echo "5. 데이터베이스에 확장 설치 중..."
export PGPASSWORD="!kdh032500"
${POSTGRES_HOME}/bin/psql -U postgres -d rag_chatbot_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 6. 확인
echo "6. 설치 확인 중..."
${POSTGRES_HOME}/bin/psql -U postgres -d rag_chatbot_db -c "\dx" | grep vector

echo ""
echo "=========================================="
echo "✓ pgvector 확장 설치 완료!"
echo "=========================================="

unset PGPASSWORD

