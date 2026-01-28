// 메인 스크립트 - ChatGPT 스타일 대화 인터페이스

// 전역 변수
let conversationHistory = [];

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    setupSidebar();
});

// 이벤트 리스너 설정
function setupEventListeners() {
    // 전송 버튼
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.addEventListener('click', handleSendMessage);

    // 입력창 Enter 키
    const userInput = document.getElementById('userInput');
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    // 파일 첨부 버튼
    const attachBtn = document.getElementById('attachBtn');
    const fileInput = document.getElementById('fileInput');
    
    attachBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });
}

// 사이드바 설정
function setupSidebar() {
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const sidebar = document.getElementById('sidebar');
    const newChatBtn = document.getElementById('newChatBtn');
    const visualizationBtn = document.getElementById('visualizationBtn');

    // 사이드바 토글
    sidebarToggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('closed');
    });

    // 새 채팅 버튼
    newChatBtn.addEventListener('click', () => {
        // 대화 히스토리 초기화
        conversationHistory = [];
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = `
            <div class="message bot-message">
                <div class="message-content">
                    무엇이 궁금한가요?
                </div>
            </div>
        `;
    });

    // 시각화 버튼
    visualizationBtn.addEventListener('click', () => {
        // 시각화 페이지로 이동
        window.location.href = 'visualization.html';
    });
}

// 메시지 전송 처리
async function handleSendMessage() {
    const userInput = document.getElementById('userInput');
    const message = userInput.value.trim();

    if (!message) return;

    // 사용자 메시지 표시
    addMessage('user', message);
    userInput.value = '';

    // 대화 히스토리 업데이트
    conversationHistory.push({
        role: 'user',
        content: message
    });

    // 로딩 표시
    const loadingId = addLoadingMessage();

    try {
        // API 클라이언트 확인
        if (!window.apiClient) {
            throw new Error('API 클라이언트가 초기화되지 않았습니다. 페이지를 새로고침해주세요.');
        }
        
        // 백엔드 API 호출
        const response = await window.apiClient.chat(message, conversationHistory);

        // 로딩 제거
        removeMessage(loadingId);

        // 봇 응답 표시
        addMessage('bot', response.answer);

        // 대화 히스토리 업데이트
        conversationHistory.push({
            role: 'assistant',
            content: response.answer
        });

        // 시각화 데이터 저장
        console.log('응답 데이터 확인:', response);
        if (response.visualizations) {
            console.log('시각화 데이터 발견:', response.visualizations);
            // Pydantic 모델이 dict로 변환되어야 함
            const vizData = response.visualizations;
            sessionStorage.setItem('visualizationData', JSON.stringify(vizData));
            console.log('시각화 데이터 저장 완료:', vizData);
            
            // 시각화 버튼 활성화 표시
            const vizBtn = document.getElementById('visualizationBtn');
            if (vizBtn) {
                if (vizData.map_points && vizData.map_points.length > 0) {
                    vizBtn.classList.add('has-data');
                    vizBtn.title = '시각화 (데이터 있음)';
                    console.log('시각화 버튼 활성화');
                } else {
                    console.warn('시각화 데이터에 map_points가 없습니다:', vizData);
                }
            }
        } else {
            console.log('응답에 시각화 데이터가 없습니다.');
        }

        // 제안 표시 (나중에 구현)
        if (response.suggestions && response.suggestions.length > 0) {
            // 제안을 채팅으로 표시할 수 있도록 준비
            // 예: "또한 다음 정보도 궁금하신가요? [제안1] [제안2]"
        }

    } catch (error) {
        console.error('메시지 처리 오류:', error);
        removeMessage(loadingId);
        addMessage('bot', `❌ 오류가 발생했습니다: ${error.message}`);
    }
}

// 파일 업로드 처리
async function handleFileUpload(file) {
    addMessage('bot', `📁 ${file.name} 파일을 업로드하는 중...`);

    try {
        if (!window.apiClient) {
            throw new Error('API 클라이언트가 초기화되지 않았습니다.');
        }
        
        const response = await window.apiClient.uploadFile(file);
        addMessage('bot', `✅ 파일이 성공적으로 업로드되었습니다. (${response.rows_imported || 0}개 데이터)`);
    } catch (error) {
        console.error('파일 업로드 오류:', error);
        addMessage('bot', `❌ 파일 업로드 실패: ${error.message}`);
    }
}

// 메시지 추가
function addMessage(role, content) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // 스크롤을 맨 아래로
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageDiv;
}

// 로딩 메시지 추가
function addLoadingMessage() {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    const messageId = 'loading_' + Date.now();
    messageDiv.id = messageId;
    messageDiv.className = 'message bot-message loading-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `
        <div class="loading-dots">
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
        </div>
        <span>답변을 생성하는 중...</span>
    `;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageId;
}

// 메시지 제거
function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

