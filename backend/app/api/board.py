"""
게시판 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models.board import Post, Comment
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


def get_client_ip(request: Request) -> str:
    """클라이언트 IP 주소 추출"""
    # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 뒤에 있을 때)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # 첫 번째 IP가 실제 클라이언트 IP
        return forwarded.split(",")[0].strip()
    
    # X-Real-IP 헤더 확인
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # 직접 연결인 경우
    if request.client:
        return request.client.host
    
    return "unknown"


# Pydantic 스키마
class PostCreate(BaseModel):
    title: str
    content: str
    author: str
    category: str = "일반"


class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    author: str
    category: str
    views: int
    likes: int
    comments_count: int
    created_at: datetime
    can_delete: bool = False  # 현재 IP로 삭제 가능 여부

    class Config:
        from_attributes = True


class PostsResponse(BaseModel):
    posts: List[PostResponse]


class CommentCreate(BaseModel):
    content: str
    author: str


class CommentResponse(BaseModel):
    id: int
    post_id: int
    content: str
    author: str
    created_at: datetime

    class Config:
        from_attributes = True


class CommentsResponse(BaseModel):
    comments: List[CommentResponse]


@router.get("/board/posts", response_model=PostsResponse)
async def get_posts(request: Request, db: Session = Depends(get_db)):
    """게시글 목록 조회"""
    try:
        client_ip = get_client_ip(request)
        posts = db.query(Post).order_by(Post.created_at.desc()).all()
        
        # 각 게시글의 댓글 수 계산
        post_list = []
        for post in posts:
            comments_count = db.query(func.count(Comment.id)).filter(
                Comment.post_id == post.id
            ).scalar()
            
            # 현재 IP가 작성자 IP와 일치하면 삭제 가능
            can_delete = (post.author_ip == client_ip)
            
            post_list.append(PostResponse(
                id=post.id,
                title=post.title,
                content=post.content,
                author=post.author,
                category=post.category,
                views=post.views or 0,
                likes=post.likes or 0,
                comments_count=comments_count or 0,
                created_at=post.created_at,
                can_delete=can_delete
            ))
        
        return PostsResponse(posts=post_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"게시글 조회 실패: {str(e)}")


@router.post("/board/posts", response_model=PostResponse)
async def create_post(post: PostCreate, request: Request, db: Session = Depends(get_db)):
    """게시글 작성"""
    try:
        client_ip = get_client_ip(request)
        
        db_post = Post(
            title=post.title,
            content=post.content,
            author=post.author,
            author_ip=client_ip,  # IP 주소 저장
            category=post.category
        )
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        
        return PostResponse(
            id=db_post.id,
            title=db_post.title,
            content=db_post.content,
            author=db_post.author,
            category=db_post.category,
            views=db_post.views or 0,
            likes=db_post.likes or 0,
            comments_count=0,
            created_at=db_post.created_at,
            can_delete=True  # 작성 직후이므로 삭제 가능
        )
    except Exception as e:
        db.rollback()
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"❌ 게시글 작성 오류: {error_msg}")
        print(error_trace)
        # 데이터베이스 관련 오류인 경우 더 자세한 메시지
        if "column" in error_msg.lower() or "table" in error_msg.lower():
            raise HTTPException(
                status_code=500, 
                detail=f"데이터베이스 오류: {error_msg}. 테이블을 확인해주세요."
            )
        raise HTTPException(status_code=500, detail=f"게시글 작성 실패: {error_msg}")


@router.post("/board/posts/{post_id}/view")
async def increment_view(post_id: int, db: Session = Depends(get_db)):
    """조회수 증가"""
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        post.views = (post.views or 0) + 1
        db.commit()
        return {"success": True, "views": post.views}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"조회수 증가 실패: {str(e)}")


@router.post("/board/posts/{post_id}/like")
async def toggle_like(post_id: int, db: Session = Depends(get_db)):
    """좋아요 토글"""
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        post.likes = (post.likes or 0) + 1
        db.commit()
        return {"success": True, "likes": post.likes}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"좋아요 실패: {str(e)}")


@router.get("/board/posts/{post_id}/comments", response_model=CommentsResponse)
async def get_comments(post_id: int, db: Session = Depends(get_db)):
    """댓글 목록 조회"""
    try:
        comments = db.query(Comment).filter(
            Comment.post_id == post_id
        ).order_by(Comment.created_at.asc()).all()
        
        return CommentsResponse(
            comments=[CommentResponse(
                id=c.id,
                post_id=c.post_id,
                content=c.content,
                author=c.author,
                created_at=c.created_at
            ) for c in comments]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"댓글 조회 실패: {str(e)}")


@router.post("/board/posts/{post_id}/comments", response_model=CommentResponse)
async def create_comment(
    post_id: int,
    comment: CommentCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """댓글 작성"""
    try:
        client_ip = get_client_ip(request)
        
        # 게시글 존재 확인
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        db_comment = Comment(
            post_id=post_id,
            content=comment.content,
            author=comment.author,
            author_ip=client_ip  # IP 주소 저장
        )
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)
        
        return CommentResponse(
            id=db_comment.id,
            post_id=db_comment.post_id,
            content=db_comment.content,
            author=db_comment.author,
            created_at=db_comment.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"댓글 작성 실패: {str(e)}")


@router.delete("/board/posts/{post_id}")
async def delete_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    """게시글 삭제 (작성자 IP만 가능)"""
    try:
        client_ip = get_client_ip(request)
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        # IP 주소 확인
        if post.author_ip != client_ip:
            raise HTTPException(
                status_code=403,
                detail="본인이 작성한 게시글만 삭제할 수 있습니다."
            )
        
        # 게시글 삭제 (댓글은 CASCADE로 자동 삭제)
        db.delete(post)
        db.commit()
        
        return {"success": True, "message": "게시글이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"게시글 삭제 실패: {str(e)}")

