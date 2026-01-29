// 메인 스크립트 - ChatGPT 스타일 대화 인터페이스

// 전역 변수
let conversationHistory = [];

// API 클라이언트 초기화 확인 및 재초기화
function ensureAPIClient() {
    if (!window.apiClient) {
        console.warn('⚠ API 클라이언트가 없습니다. 재초기화 시도...');
        // client.js가 다시 로드되지 않으므로 수동으로 초기화
        if (typeof APIClient !== 'undefined') {
            window.apiClient = new APIClient();
            console.log('✓ API 클라이언트 재초기화 완료:', window.apiClient.baseURL);
        } else {
            console.error('❌ APIClient 클래스를 찾을 수 없습니다. 페이지를 새로고침해주세요.');
            return false;
        }
    } else {
        console.log('✓ API 클라이언트 확인됨:', window.apiClient.baseURL);
    }
    return true;
}

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('=== 페이지 로드 시작 ===');
    
    // API 클라이언트 초기화 확인
    ensureAPIClient();
    
    // 새로고침 감지 (Performance Navigation API 사용)
    let isReload = false;
    try {
        const navEntry = performance.getEntriesByType('navigation')[0];
        if (navEntry) {
            isReload = navEntry.type === 'reload';
            console.log(`페이지 로드 타입: ${navEntry.type}`);
        }
    } catch (e) {
        // Performance API를 지원하지 않는 브라우저 대응
        console.warn('Performance API를 사용할 수 없습니다:', e);
    }
    
    if (isReload) {
        console.log('🔄 새로고침 감지: 대화 히스토리 초기화');
        // 새로고침 시 sessionStorage 초기화
        sessionStorage.removeItem('conversationHistory');
        sessionStorage.removeItem('visualizationData');
        conversationHistory = [];
    } else {
        console.log('📄 일반 페이지 로드: 대화 히스토리 복원');
        // sessionStorage에서 대화 히스토리 복원
        loadConversationHistory();
    }
    
    setupEventListeners();
    setupSidebar();
    
    // 항상 메시지 복원 (히스토리가 없으면 초기 메시지 표시)
    restoreChatMessages();
    
    console.log('=== 페이지 로드 완료 ===');
});

// 페이지 언로드 전에 히스토리 저장
// 주의: beforeunload에서는 navigation type을 정확히 감지하기 어려우므로
// 항상 저장하되, 새로고침 시에는 DOMContentLoaded에서 초기화
window.addEventListener('beforeunload', () => {
    console.log('페이지 언로드: 히스토리 저장');
    saveConversationHistory();
});

// 페이지 숨김 시에도 저장 (모바일/탭 전환 대응)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('페이지 숨김: 히스토리 저장');
        saveConversationHistory();
    }
});

// sessionStorage에서 대화 히스토리 로드
function loadConversationHistory() {
    try {
        console.log('=== 히스토리 로드 시작 ===');
        const stored = sessionStorage.getItem('conversationHistory');
        
        if (stored) {
            console.log(`sessionStorage 확인: 데이터 있음 (${stored.length} bytes)`);
            conversationHistory = JSON.parse(stored);
            console.log(`✓ 대화 히스토리 로드 성공: ${conversationHistory.length}개 메시지`);
            
            // 디버깅: 첫 번째와 마지막 메시지 확인
            if (conversationHistory.length > 0) {
                console.log(`  첫 메시지: ${conversationHistory[0].role} - ${conversationHistory[0].content.substring(0, 50)}...`);
                console.log(`  마지막 메시지: ${conversationHistory[conversationHistory.length - 1].role} - ${conversationHistory[conversationHistory.length - 1].content.substring(0, 50)}...`);
            }
        } else {
            conversationHistory = [];
            console.log('sessionStorage 확인: 데이터 없음');
            console.log('새 대화 시작 (히스토리 없음)');
        }
        console.log('=== 히스토리 로드 완료 ===');
    } catch (e) {
        console.error('대화 히스토리 로드 실패:', e);
        conversationHistory = [];
    }
}

// sessionStorage에 대화 히스토리 저장
function saveConversationHistory() {
    try {
        const jsonData = JSON.stringify(conversationHistory);
        sessionStorage.setItem('conversationHistory', jsonData);
        console.log(`✓ 대화 히스토리 저장 완료: ${conversationHistory.length}개 메시지 (${jsonData.length} bytes)`);
        
        // 저장 확인
        const verify = sessionStorage.getItem('conversationHistory');
        if (verify) {
            console.log(`  저장 확인: ${verify.length} bytes 저장됨`);
        } else {
            console.warn('  저장 확인 실패: sessionStorage에 데이터가 없습니다.');
        }
    } catch (e) {
        console.error('대화 히스토리 저장 실패:', e);
        // QuotaExceededError 등 처리
        if (e.name === 'QuotaExceededError') {
            console.error('sessionStorage 용량 초과!');
        }
    }
}

// 복원된 히스토리로 메시지 표시
function restoreChatMessages() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) {
        console.warn('chatMessages 요소를 찾을 수 없습니다.');
        return;
    }
    
    console.log(`메시지 복원 시작: 히스토리 ${conversationHistory.length}개`);
    
    // 기존 메시지 모두 제거 (초기 메시지 포함)
    chatMessages.innerHTML = '';
    
    // 히스토리가 비어있으면 초기 메시지 표시
    if (conversationHistory.length === 0) {
        console.log('히스토리 없음: 초기 메시지 표시');
        chatMessages.innerHTML = `
            <div class="message bot-message">
                <div class="message-content">
                    무엇이 궁금한가요?
                </div>
            </div>
        `;
        return;
    }
    
    // 히스토리에서 메시지 복원
    console.log('히스토리에서 메시지 복원 중...');
    let restoredCount = 0;
    conversationHistory.forEach((msg, index) => {
        try {
            // addMessage 함수가 'assistant'를 'bot'으로 자동 변환하므로 그대로 전달
            const result = addMessage(msg.role, msg.content, false); // 스크롤 없이 추가
            
            if (result) {
                restoredCount++;
                if (index < 3 || index >= conversationHistory.length - 3) {
                    // 처음 3개와 마지막 3개만 로그 출력
                    console.log(`  [${index + 1}/${conversationHistory.length}] ${msg.role}: ${msg.content.substring(0, 50)}...`);
                }
            } else {
                console.error(`  메시지 ${index + 1} 추가 실패`);
            }
        } catch (e) {
            console.error(`  메시지 ${index + 1} 복원 실패:`, e);
        }
    });
    
    // 마지막에 스크롤
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 100);
    
    console.log(`✓ ${restoredCount}/${conversationHistory.length}개 메시지 복원 완료`);
    console.log(`=== 메시지 복원 완료 ===`);
}

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
        sessionStorage.removeItem('conversationHistory');
        sessionStorage.removeItem('visualizationData');
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = `
            <div class="message bot-message">
                <div class="message-content">
                    무엇이 궁금한가요?
                </div>
            </div>
        `;
        console.log('✓ 새 채팅 시작 (히스토리 초기화)');
    });

    // 시각화 버튼
    visualizationBtn.addEventListener('click', () => {
        // 현재 히스토리 저장 (시각화 페이지로 이동 전)
        console.log('시각화 버튼 클릭: 현재 히스토리 저장');
        console.log(`  저장할 히스토리: ${conversationHistory.length}개 메시지`);
        saveConversationHistory();
        
        // 저장 확인
        const verify = sessionStorage.getItem('conversationHistory');
        if (verify) {
            console.log(`  저장 확인: ${verify.length} bytes 저장됨`);
        } else {
            console.error('  저장 실패: sessionStorage에 데이터가 없습니다!');
        }
        
        // 약간의 지연 후 이동 (저장 완료 보장)
        setTimeout(() => {
            console.log('시각화 페이지로 이동');
            window.location.href = 'visualization.html';
        }, 100);
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

    // 대화 히스토리 업데이트 및 즉시 저장
    conversationHistory.push({
        role: 'user',
        content: message
    });
    saveConversationHistory(); // 즉시 저장

    // 로딩 표시
    const loadingId = addLoadingMessage();

    try {
        // API 클라이언트 확인 및 재초기화 시도
        if (!ensureAPIClient()) {
            throw new Error('API 클라이언트를 초기화할 수 없습니다. 페이지를 새로고침해주세요.');
        }
        
        // 백엔드 API 호출
        const response = await window.apiClient.chat(message, conversationHistory);

        // 로딩 제거
        removeMessage(loadingId);

        // 봇 응답 표시
        addMessage('bot', response.answer);

        // 대화 히스토리 업데이트 및 즉시 저장
        conversationHistory.push({
            role: 'assistant',
            content: response.answer
        });
        saveConversationHistory(); // 즉시 저장

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
function addMessage(role, content, scroll = true) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) {
        console.error('chatMessages 요소를 찾을 수 없습니다.');
        return null;
    }
    
    const messageDiv = document.createElement('div');
    
    // role 변환: 'assistant' -> 'bot', 'user' -> 'user'
    let messageRole = role;
    if (role === 'assistant') {
        messageRole = 'bot';
    }
    
    messageDiv.className = `message ${messageRole}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // 스크롤을 맨 아래로 (scroll이 true일 때만)
    if (scroll) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
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

