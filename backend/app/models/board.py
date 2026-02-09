"""
게시판 모델 - 게시글 및 댓글
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Post(Base):
    """게시글 테이블"""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)  # 제목
    content = Column(Text, nullable=False)  # 내용
    author = Column(String(100), nullable=False)  # 작성자 이름
    author_ip = Column(String(45), nullable=False, index=True)  # 작성자 IP 주소 (IPv6 지원)
    category = Column(String(20), nullable=False, default="일반", index=True)  # 카테고리
    views = Column(Integer, default=0)  # 조회수
    likes = Column(Integer, default=0)  # 좋아요 수
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 작성일
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # 수정일

    # 관계
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Post(id={self.id}, title='{self.title[:30]}...', author='{self.author}')>"


class Comment(Base):
    """댓글 테이블"""
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)  # 댓글 내용
    author = Column(String(100), nullable=False)  # 작성자 이름
    author_ip = Column(String(45), nullable=False, index=True)  # 작성자 IP 주소 (IPv6 지원)
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 작성일

    # 관계
    post = relationship("Post", back_populates="comments")

    def __repr__(self):
        return f"<Comment(id={self.id}, post_id={self.post_id}, author='{self.author}')>"

