// 게시판 JavaScript

// 전역 변수
let posts = [];
let currentSort = 'latest';
let selectedPost = null;

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('게시판 페이지 로드');
    setupSidebar();
    setupBoard();
    loadPosts();
});

// 사이드바 설정
function setupSidebar() {
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const sidebar = document.getElementById('sidebar');
    const chatBtn = document.getElementById('chatBtn');
    const visualizationBtn = document.getElementById('visualizationBtn');
    const boardBtn = document.getElementById('boardBtn');

    // 사이드바 토글
    sidebarToggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('closed');
    });

    // 채팅 버튼
    chatBtn.addEventListener('click', () => {
        window.location.href = 'index.html';
    });

    // 시각화 버튼
    visualizationBtn.addEventListener('click', () => {
        window.location.href = 'visualization.html';
    });

    // 게시판 버튼 (현재 페이지)
    boardBtn.classList.add('active');
}

// 게시판 설정
function setupBoard() {
    // 정렬 버튼
    const sortBtns = document.querySelectorAll('.sort-btn');
    sortBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            sortBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSort = btn.dataset.sort;
            renderPosts();
        });
    });

    // 게시글 작성 버튼
    const createPostBtn = document.getElementById('createPostBtn');
    createPostBtn.addEventListener('click', () => {
        openCreateModal();
    });

    // 모달 닫기
    const closeCreateModal = document.getElementById('closeCreateModal');
    const cancelCreatePost = document.getElementById('cancelCreatePost');
    const createPostModal = document.getElementById('createPostModal');
    
    closeCreateModal.addEventListener('click', () => {
        closeCreateModalFunc();
    });
    cancelCreatePost.addEventListener('click', () => {
        closeCreateModalFunc();
    });
    createPostModal.addEventListener('click', (e) => {
        if (e.target === createPostModal) {
            closeCreateModal();
        }
    });

    // 게시글 작성 폼
    const createPostForm = document.getElementById('createPostForm');
    createPostForm.addEventListener('submit', handleCreatePost);

    // 게시글 상세 모달 닫기
    const closeDetailModal = document.getElementById('closeDetailModal');
    const postDetailModal = document.getElementById('postDetailModal');
    
    closeDetailModal.addEventListener('click', () => {
        closePostDetailModal();
    });
    postDetailModal.addEventListener('click', (e) => {
        if (e.target === postDetailModal) {
            closePostDetailModal();
        }
    });
}

// 게시글 로드
async function loadPosts() {
    try {
        if (!window.apiClient) {
            console.error('API 클라이언트가 없습니다.');
            return;
        }

        const response = await fetch(`${window.apiClient.baseURL}/api/board/posts`);
        if (!response.ok) {
            throw new Error(`API 오류: ${response.status}`);
        }

        const data = await response.json();
        posts = data.posts || [];
        renderPosts();
    } catch (error) {
        console.error('게시글 로드 실패:', error);
        // 오류 시 빈 배열로 시작
        posts = [];
        renderPosts();
    }
}

// 게시글 렌더링
function renderPosts() {
    const boardList = document.getElementById('boardList');
    
    if (posts.length === 0) {
        boardList.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 7h16M4 12h16M4 17h16"></path>
                </svg>
                <p>아직 게시글이 없습니다.<br>첫 게시글을 작성해보세요!</p>
            </div>
        `;
        return;
    }

    // 정렬
    const sortedPosts = [...posts].sort((a, b) => {
        if (currentSort === 'latest') {
            return new Date(b.created_at) - new Date(a.created_at);
        } else {
            return (b.views || 0) - (a.views || 0);
        }
    });

    boardList.innerHTML = sortedPosts.map(post => `
        <div class="board-item" data-post-id="${post.id}">
            <div class="board-item-header">
                <span class="post-category-badge ${getCategoryClass(post.category)}">${post.category}</span>
                ${post.category === '공지' ? '<span class="post-notice-label">필독</span>' : ''}
                ${post.can_delete ? `<button class="delete-post-btn" data-post-id="${post.id}" onclick="event.stopPropagation(); handleDeletePost(${post.id})" title="삭제">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>` : ''}
            </div>
            <div class="board-item-title">${escapeHtml(post.title)}</div>
            <div class="board-item-content">${escapeHtml(post.content)}</div>
            <div class="board-item-footer">
                <span class="board-item-author">${escapeHtml(post.author)}</span>
                <span>${formatDate(post.created_at)}</span>
                <div class="board-item-meta">
                    <span class="board-item-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                        ${post.views || 0}
                    </span>
                    <span class="board-item-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 9V5a3 3 0 0 0-6 0v4"></path>
                            <rect x="4" y="9" width="16" height="11" rx="2" ry="2"></rect>
                            <path d="M9 14h6"></path>
                        </svg>
                        ${post.likes || 0}
                    </span>
                    <span class="board-item-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                        </svg>
                        ${post.comments_count || 0}
                    </span>
                </div>
            </div>
        </div>
    `).join('');

    // 게시글 클릭 이벤트
    boardList.querySelectorAll('.board-item').forEach(item => {
        item.addEventListener('click', () => {
            const postId = parseInt(item.dataset.postId);
            const post = posts.find(p => p.id === postId);
            if (post) {
                openPostDetail(post);
            }
        });
    });
}

// 카테고리 클래스 반환
function getCategoryClass(category) {
    const classes = {
        '공지': 'notice',
        '대기질': 'air',
        '수질': 'water',
        '토양': 'soil',
        '일반': 'general'
    };
    return classes[category] || 'general';
}

// 게시글 작성 모달 열기
function openCreateModal() {
    const modal = document.getElementById('createPostModal');
    modal.classList.add('active');
    document.getElementById('postAuthor').value = '';
    document.getElementById('postTitle').value = '';
    document.getElementById('postContent').value = '';
    document.getElementById('postCategory').value = '일반';
}

// 게시글 작성 모달 닫기
function closeCreateModalFunc() {
    const modal = document.getElementById('createPostModal');
    modal.classList.remove('active');
}

// 게시글 작성 처리
async function handleCreatePost(e) {
    e.preventDefault();
    
    const title = document.getElementById('postTitle').value.trim();
    const content = document.getElementById('postContent').value.trim();
    const author = document.getElementById('postAuthor').value.trim();
    const category = document.getElementById('postCategory').value;

    if (!title || !content || !author) {
        alert('모든 필드를 입력해주세요.');
        return;
    }

    try {
        if (!window.apiClient) {
            throw new Error('API 클라이언트가 없습니다.');
        }

        const response = await fetch(`${window.apiClient.baseURL}/api/board/posts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title,
                content,
                author,
                category
            })
        });

        if (!response.ok) {
            let errorMessage = `API 오류: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorMessage;
                console.error('API 오류 상세:', errorData);
            } catch (e) {
                const text = await response.text();
                console.error('API 오류 응답:', text);
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        console.log('게시글 작성 성공:', data);
        
        closeCreateModalFunc();
        loadPosts(); // 게시글 목록 새로고침
    } catch (error) {
        console.error('게시글 작성 실패:', error);
        const errorMessage = error.message || '게시글 작성에 실패했습니다.';
        alert(`게시글 작성 실패\n\n${errorMessage}\n\n브라우저 콘솔(F12)을 확인해주세요.`);
    }
}

// 게시글 상세 모달 열기
async function openPostDetail(post) {
    selectedPost = post;
    const modal = document.getElementById('postDetailModal');
    const content = document.getElementById('postDetailContent');
    
    // 조회수 증가
    try {
        await fetch(`${window.apiClient.baseURL}/api/board/posts/${post.id}/view`, {
            method: 'POST'
        });
    } catch (error) {
        console.error('조회수 증가 실패:', error);
    }

    // 댓글 로드
    let comments = [];
    try {
        const commentsResponse = await fetch(`${window.apiClient.baseURL}/api/board/posts/${post.id}/comments`);
        if (commentsResponse.ok) {
            const commentsData = await commentsResponse.json();
            comments = commentsData.comments || [];
        }
    } catch (error) {
        console.error('댓글 로드 실패:', error);
    }

    content.innerHTML = `
        <h1 class="post-detail-title">${escapeHtml(post.title)}</h1>
        <div class="post-detail-meta">
            <div class="post-detail-author">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
                ${escapeHtml(post.author)}
            </div>
            <span>${formatDate(post.created_at)}</span>
            <div class="board-item-meta">
                <span class="board-item-meta-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    ${post.views || 0}
                </span>
                <span class="board-item-meta-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 9V5a3 3 0 0 0-6 0v4"></path>
                        <rect x="4" y="9" width="16" height="11" rx="2" ry="2"></rect>
                        <path d="M9 14h6"></path>
                    </svg>
                    ${post.likes || 0}
                </span>
            </div>
        </div>
        <div class="post-detail-content">${escapeHtml(post.content)}</div>
        <div class="post-detail-actions">
            <button class="like-btn" data-post-id="${post.id}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 9V5a3 3 0 0 0-6 0v4"></path>
                    <rect x="4" y="9" width="16" height="11" rx="2" ry="2"></rect>
                    <path d="M9 14h6"></path>
                </svg>
                좋아요 ${post.likes || 0}
            </button>
            ${post.can_delete ? `<button class="delete-post-btn-detail" onclick="handleDeletePost(${post.id})">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                삭제
            </button>` : ''}
        </div>
        <div class="comments-section">
            <h3 class="comments-title">댓글 ${comments.length}</h3>
            <div class="comment-list">
                ${comments.map(comment => `
                    <div class="comment-item">
                        <div class="comment-header">
                            <div class="comment-author">${escapeHtml(comment.author)}</div>
                            <div class="comment-date">${formatDate(comment.created_at)}</div>
                        </div>
                        <div class="comment-content">${escapeHtml(comment.content)}</div>
                    </div>
                `).join('')}
            </div>
            <div class="comment-form">
                <textarea id="newComment" placeholder="댓글을 입력하세요..."></textarea>
                <button onclick="handleAddComment(${post.id})">댓글 작성</button>
            </div>
        </div>
    `;

    document.getElementById('detailCategory').textContent = post.category;
    document.getElementById('detailCategory').className = `post-category-badge ${getCategoryClass(post.category)}`;

    // 좋아요 버튼 이벤트
    const likeBtn = content.querySelector('.like-btn');
    if (likeBtn) {
        likeBtn.addEventListener('click', () => {
            handleLike(post.id);
        });
    }

    modal.classList.add('active');
}

// 게시글 상세 모달 닫기
function closePostDetailModal() {
    const modal = document.getElementById('postDetailModal');
    modal.classList.remove('active');
    selectedPost = null;
}

// 좋아요 처리
async function handleLike(postId) {
    try {
        const response = await fetch(`${window.apiClient.baseURL}/api/board/posts/${postId}/like`, {
            method: 'POST'
        });

        if (response.ok) {
            loadPosts();
            if (selectedPost && selectedPost.id === postId) {
                openPostDetail(selectedPost);
            }
        }
    } catch (error) {
        console.error('좋아요 실패:', error);
    }
}

// 댓글 추가
async function handleAddComment(postId) {
    const commentInput = document.getElementById('newComment');
    const content = commentInput.value.trim();

    if (!content) {
        alert('댓글 내용을 입력해주세요.');
        return;
    }

    try {
        const response = await fetch(`${window.apiClient.baseURL}/api/board/posts/${postId}/comments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content,
                author: '사용자' // 나중에 사용자 인증 추가
            })
        });

        if (response.ok) {
            commentInput.value = '';
            loadPosts();
            if (selectedPost && selectedPost.id === postId) {
                openPostDetail(selectedPost);
            }
        } else {
            throw new Error('댓글 작성 실패');
        }
    } catch (error) {
        console.error('댓글 작성 실패:', error);
        alert('댓글 작성에 실패했습니다.');
    }
}

// 유틸리티 함수
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 게시글 삭제
async function handleDeletePost(postId) {
    if (!confirm('정말 이 게시글을 삭제하시겠습니까?')) {
        return;
    }

    try {
        const response = await fetch(`${window.apiClient.baseURL}/api/board/posts/${postId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '삭제 실패');
        }

        const result = await response.json();
        alert('게시글이 삭제되었습니다.');
        
        // 모달 닫기
        closePostDetailModal();
        
        // 게시글 목록 새로고침
        loadPosts();
    } catch (error) {
        console.error('게시글 삭제 실패:', error);
        alert(error.message || '게시글 삭제에 실패했습니다.');
    }
}

// 전역 함수로 등록 (인라인 이벤트 핸들러용)
window.handleAddComment = handleAddComment;
window.handleDeletePost = handleDeletePost;

