// 백엔드 설정
const CONFIG = {
    // 백엔드 API URL - 현재 호스트를 자동으로 감지
    // ngrok URL로 접속하면 자동으로 같은 호스트 사용
    BACKEND_API_URL: (function() {
        // 현재 페이지의 호스트를 사용 (ngrok URL 포함)
        const host = window.location.hostname;
        const protocol = window.location.protocol;
        const port = window.location.port;
        
        // ngrok URL인 경우 (ngrok-free.app 또는 ngrok.io 도메인)
        if (host.includes('ngrok-free.app') || host.includes('ngrok.io') || host.includes('ngrok.dev')) {
            // ngrok은 443으로 접속하므로 같은 호스트만 사용 (포트 없음)
            return `${protocol}//${host}`;
        }
        
        // 로컬 개발 환경
        if (host === 'localhost' || host === '127.0.0.1') {
            return 'http://localhost:8000';
        }
        
        // 기타 환경 (프로덕션 등)
        return `${protocol}//${host}${port ? ':' + port : ''}`;
    })(),
    
    // API 엔드포인트
    API_ENDPOINTS: {
        CHAT: '/api/chat',
        UPLOAD: '/api/upload'
    }
};

// 전역으로 내보내기
window.CONFIG = CONFIG;

