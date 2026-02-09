#!/bin/bash

# GitHub Actions 배포 설정 도우미 스크립트
# 이 스크립트는 SSH 키 생성과 서버 설정을 도와줍니다.

set -e

echo "🚀 GitHub Actions 배포 설정 시작..."
echo ""

# 1. SSH 키 생성
echo "1️⃣ SSH 키 생성 중..."
SSH_KEY_PATH="$HOME/.ssh/github_actions_deploy"

if [ ! -f "$SSH_KEY_PATH" ]; then
    ssh-keygen -t ed25519 -C "github-actions-deploy" -f "$SSH_KEY_PATH" -N ""
    echo "✅ SSH 키 생성 완료: $SSH_KEY_PATH"
else
    echo "⚠️  SSH 키가 이미 존재합니다: $SSH_KEY_PATH"
    read -p "기존 키를 사용하시겠습니까? (y/n): " use_existing
    if [ "$use_existing" != "y" ]; then
        exit 1
    fi
fi

echo ""
echo "2️⃣ 공개키 내용:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$SSH_KEY_PATH.pub"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 위 공개키를 서버에 복사해야 합니다."
echo ""

# 2. 서버 정보 입력
read -p "서버 IP 주소 또는 호스트명: " SERVER_HOST
read -p "SSH 사용자명 (기본값: pi): " SERVER_USER
SERVER_USER=${SERVER_USER:-pi}
read -p "SSH 포트 (기본값: 22): " SERVER_PORT
SERVER_PORT=${SERVER_PORT:-22}

echo ""
echo "3️⃣ 서버에 공개키 복사 중..."
ssh-copy-id -i "$SSH_KEY_PATH.pub" -p "$SERVER_PORT" "$SERVER_USER@$SERVER_HOST" || {
    echo "❌ 공개키 복사 실패"
    echo ""
    echo "수동으로 복사하세요:"
    echo "1. 다음 명령어로 공개키 내용 확인:"
    echo "   cat $SSH_KEY_PATH.pub"
    echo ""
    echo "2. 서버에 SSH 접속:"
    echo "   ssh $SERVER_USER@$SERVER_HOST"
    echo ""
    echo "3. 서버에서 실행:"
    echo "   mkdir -p ~/.ssh"
    echo "   echo '공개키_내용' >> ~/.ssh/authorized_keys"
    echo "   chmod 600 ~/.ssh/authorized_keys"
    echo "   chmod 700 ~/.ssh"
    exit 1
}

echo "✅ 공개키 복사 완료!"

# 3. SSH 접속 테스트
echo ""
echo "4️⃣ SSH 접속 테스트 중..."
ssh -i "$SSH_KEY_PATH" -p "$SERVER_PORT" "$SERVER_USER@$SERVER_HOST" "echo 'SSH 접속 성공!'" || {
    echo "❌ SSH 접속 실패"
    exit 1
}
echo "✅ SSH 접속 테스트 성공!"

# 4. 개인키 내용 출력
echo ""
echo "5️⃣ GitHub Secrets 설정 정보:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 GitHub 저장소 → Settings → Secrets and variables → Actions"
echo ""
echo "다음 Secrets를 추가하세요:"
echo ""
echo "1. SERVER_HOST"
echo "   Value: $SERVER_HOST"
echo ""
echo "2. SERVER_USER"
echo "   Value: $SERVER_USER"
echo ""
echo "3. SERVER_PORT (선택사항)"
echo "   Value: $SERVER_PORT"
echo ""
echo "4. SERVER_SSH_KEY"
echo "   Value: (아래 개인키 전체 내용)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "개인키 내용 (전체 복사):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$SSH_KEY_PATH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  개인키는 절대 공개하지 마세요!"
echo ""

# 5. 프로젝트 경로 확인
read -p "서버의 프로젝트 경로 (기본값: /home/$SERVER_USER/rag-chatbot): " PROJECT_PATH
PROJECT_PATH=${PROJECT_PATH:-/home/$SERVER_USER/rag-chatbot}

echo ""
echo "6️⃣ 추가 Secret (선택사항):"
echo "   PROJECT_PATH"
echo "   Value: $PROJECT_PATH"
echo ""

echo "✅ 설정 완료!"
echo ""
echo "다음 단계:"
echo "1. GitHub Secrets에 위 정보 입력"
echo "2. .github/workflows/deploy.yml 파일 확인"
echo "3. 테스트 배포 실행: git push origin main"
echo ""

