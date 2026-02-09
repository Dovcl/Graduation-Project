#!/usr/bin/env python3
"""
GitHub Webhook 서버
GitHub에 푸시하면 자동으로 배포 스크립트 실행
"""
import subprocess
import hmac
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os

# 설정
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-secret-key")  # GitHub Webhook Secret
DEPLOY_SCRIPT = os.path.join(os.path.dirname(__file__), "auto_deploy.sh")
PORT = int(os.getenv("WEBHOOK_PORT", "9000"))


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """GitHub Webhook 요청 처리"""
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        # 요청 본문 읽기
        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)
        
        # GitHub 서명 확인 (선택사항, 보안 강화)
        signature = self.headers.get("X-Hub-Signature-256", "")
        if signature:
            expected_signature = "sha256=" + hmac.new(
                WEBHOOK_SECRET.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Invalid signature")
                return

        # JSON 파싱
        try:
            event = json.loads(payload.decode())
        except:
            self.send_response(400)
            self.end_headers()
            return

        # push 이벤트만 처리
        if self.headers.get("X-GitHub-Event") == "push":
            print(f"📥 Push 이벤트 수신: {event.get('ref', 'unknown')}")
            
            # 배포 스크립트 실행
            try:
                result = subprocess.run(
                    ["bash", DEPLOY_SCRIPT],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5분 타임아웃
                )
                
                if result.returncode == 0:
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    response = {"status": "success", "message": "배포 완료"}
                    self.wfile.write(json.dumps(response).encode())
                    print("✅ 배포 성공")
                else:
                    self.send_response(500)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    response = {
                        "status": "error",
                        "message": "배포 실패",
                        "error": result.stderr
                    }
                    self.wfile.write(json.dumps(response).encode())
                    print(f"❌ 배포 실패: {result.stderr}")
            except subprocess.TimeoutExpired:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Deployment timeout")
                print("❌ 배포 타임아웃")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
                print(f"❌ 배포 오류: {e}")
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Ignored event")

    def do_GET(self):
        """헬스 체크"""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Webhook server is running")

    def log_message(self, format, *args):
        """로그 메시지 출력"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    """웹훅 서버 시작"""
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"🚀 GitHub Webhook 서버 시작: http://0.0.0.0:{PORT}/webhook")
    print(f"📝 배포 스크립트: {DEPLOY_SCRIPT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 서버 종료")
        server.shutdown()


if __name__ == "__main__":
    main()

