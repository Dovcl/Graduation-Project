// API 클라이언트 - 백엔드 호출만 담당

class APIClient {
    constructor() {
        this.baseURL = window.CONFIG?.BACKEND_API_URL || 'http://localhost:8000';
    }

    /**
     * 채팅 메시지 전송
     * @param {string} message - 사용자 메시지
     * @param {Array} history - 대화 히스토리 (선택)
     * @returns {Promise<Object>} 응답 데이터
     */
    async chat(message, history = []) {
        try {
            const endpoint = window.CONFIG?.API_ENDPOINTS?.CHAT || '/api/chat';
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    history: history
                })
            });

            if (!response.ok) {
                throw new Error(`API 오류: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API 호출 실패:', error);
            throw error;
        }
    }

    /**
     * 파일 업로드
     * @param {File} file - 업로드할 파일
     * @returns {Promise<Object>} 업로드 결과
     */
    async uploadFile(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const endpoint = window.CONFIG?.API_ENDPOINTS?.UPLOAD || '/api/upload';
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`업로드 오류: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('파일 업로드 실패:', error);
            throw error;
        }
    }
}

// 싱글톤 인스턴스 생성 및 전역 등록
(function() {
    const apiClient = new APIClient();
    window.apiClient = apiClient;
    
    // 초기화 확인 로그
    console.log('API 클라이언트 초기화 완료:', apiClient.baseURL);
})();

