// 백엔드 설정
const CONFIG = {
    // 백엔드 API URL
    BACKEND_API_URL: 'http://localhost:8000',
    
    // API 엔드포인트
    API_ENDPOINTS: {
        CHAT: '/api/chat',
        UPLOAD: '/api/upload'
    }
};

// 전역으로 내보내기
window.CONFIG = CONFIG;

