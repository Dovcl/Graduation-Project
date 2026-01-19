"""
LangChain 기반 RAG 검색 서비스
문서 청킹, 임베딩, 벡터 검색을 LangChain으로 처리
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
from sqlalchemy.orm import Session

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, CSVLoader
from langchain_community.vectorstores import PGVector
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document as LangChainDocument
import pandas as pd
import pdfplumber
import json
import html

from app.database import get_db
from app.core.config import settings


class RAGServiceLangChain:
    """LangChain 기반 RAG 검색 서비스"""
    
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # 청크 크기
            chunk_overlap=50,  # 청크 간 겹침
            length_function=len,
            separators=["\n\n", "\n", " ", ""]  # 분리 기준
        )
        
        # 임베딩 모델 (sentence-transformers 사용)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}  # 코사인 유사도 사용 시 정규화 권장
        )
        
        # 벡터 스토어 연결 문자열
        self.connection_string = settings.DATABASE_URL
    
    def load_excel_file(
        self, 
        file_path: str, 
        sheet_name: Optional[str] = None
    ) -> List[LangChainDocument]:
        """
        엑셀 파일을 로드하여 Document 리스트로 변환
        
        Args:
            file_path: 엑셀 파일 경로
            sheet_name: 시트 이름 (None이면 모든 시트)
        
        Returns:
            Document 리스트
        """
        try:
            documents = []
            
            # pandas로 엑셀 읽기
            if sheet_name:
                # 특정 시트만 읽기
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                content = f"시트: {sheet_name}\n\n{df.to_string()}"
                doc = LangChainDocument(
                    page_content=content,
                    metadata={
                        "source": file_path,
                        "doc_type": "excel",
                        "sheet_name": sheet_name
                    }
                )
                documents.append(doc)
            else:
                # 모든 시트 읽기
                excel_file = pd.ExcelFile(file_path)
                for sheet in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    content = f"시트: {sheet}\n\n{df.to_string()}"
                    doc = LangChainDocument(
                        page_content=content,
                        metadata={
                            "source": file_path,
                            "doc_type": "excel",
                            "sheet_name": sheet
                        }
                    )
                    documents.append(doc)
            
            return documents
        except Exception as e:
            print(f"엑셀 파일 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def load_text_file(self, file_path: str) -> List[LangChainDocument]:
        """텍스트 파일 로드"""
        try:
            loader = TextLoader(file_path, encoding='utf-8')
            documents = loader.load()
            for doc in documents:
                doc.metadata["source"] = file_path
                doc.metadata["doc_type"] = "text"
            return documents
        except Exception as e:
            print(f"텍스트 파일 로드 오류: {e}")
            return []
    
    def load_pdf_file(
        self,
        file_path: str,
        extract_tables: bool = True
    ) -> List[LangChainDocument]:
        """
        PDF 파일을 로드하여 Document 리스트로 변환
        스크린샷의 최적화 방법 적용:
        1. 텍스트 부분은 Markdown 변환
        2. 표는 HTML/JSON으로 저장 + 메타데이터 추가
        
        Args:
            file_path: PDF 파일 경로
            extract_tables: 표 추출 여부
        
        Returns:
            Document 리스트 (텍스트 + 표)
        """
        try:
            documents = []
            
            with pdfplumber.open(file_path) as pdf:
                print(f"PDF 로드: {len(pdf.pages)}페이지")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # 1. 텍스트 추출 (Markdown 변환)
                    text = page.extract_text()
                    if text and text.strip():
                        # 텍스트를 Document로 저장
                        doc = LangChainDocument(
                            page_content=text,
                            metadata={
                                "source": file_path,
                                "doc_type": "pdf_text",
                                "page_number": page_num,
                                "content_type": "text"
                            }
                        )
                        documents.append(doc)
                    
                    # 2. 표 추출 (HTML/JSON 변환)
                    if extract_tables:
                        tables = page.extract_tables()
                        for table_num, table in enumerate(tables, 1):
                            if table and len(table) > 0:
                                # 표를 HTML로 변환
                                html_table = self._table_to_html(table)
                                
                                # 표를 JSON으로도 변환
                                json_table = json.dumps(table, ensure_ascii=False, indent=2)
                                
                                # HTML 표를 Document로 저장
                                table_content = f"표 {table_num} (페이지 {page_num}):\n\n{html_table}\n\nJSON 형식:\n{json_table}"
                                
                                doc = LangChainDocument(
                                    page_content=table_content,
                                    metadata={
                                        "source": file_path,
                                        "doc_type": "pdf_table",
                                        "page_number": page_num,
                                        "table_number": table_num,
                                        "content_type": "table",
                                        "table_html": html_table,
                                        "table_json": json_table,
                                        "table_rows": len(table),
                                        "table_cols": len(table[0]) if table else 0
                                    }
                                )
                                documents.append(doc)
                                
                                print(f"  페이지 {page_num}: 표 {table_num} 추출 ({len(table)}행)")
            
            print(f"✓ PDF 로드 완료: 텍스트 {len([d for d in documents if d.metadata.get('content_type') == 'text'])}개, 표 {len([d for d in documents if d.metadata.get('content_type') == 'table'])}개")
            return documents
        
        except Exception as e:
            print(f"PDF 파일 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _table_to_html(self, table: List[List[str]]) -> str:
        """표를 HTML 형식으로 변환"""
        if not table or len(table) == 0:
            return ""
        
        html_rows = []
        for i, row in enumerate(table):
            cells = []
            for cell in row:
                cell_text = str(cell) if cell is not None else ""
                cell_text = html.escape(cell_text)
                tag = "th" if i == 0 else "td"  # 첫 행은 헤더
                cells.append(f"<{tag}>{cell_text}</{tag}>")
            html_rows.append(f"<tr>{''.join(cells)}</tr>")
        
        return f"<table>{''.join(html_rows)}</table>"
    
    def chunk_documents(
        self, 
        documents: List[LangChainDocument]
    ) -> List[LangChainDocument]:
        """
        문서를 작은 청크로 분할
        
        Args:
            documents: 원본 문서 리스트
        
        Returns:
            청크로 나뉜 문서 리스트
        """
        chunks = self.text_splitter.split_documents(documents)
        return chunks
    
    def index_documents(
        self,
        documents: List[LangChainDocument],
        collection_name: str = "documents",
        db: Session = None
    ) -> PGVector:
        """
        문서를 벡터화하여 PGVector에 저장
        
        Args:
            documents: 문서 리스트
            collection_name: 컬렉션 이름
            db: 데이터베이스 세션 (사용 안 함, connection_string 사용)
        
        Returns:
            PGVector 인스턴스
        """
        # 문서 청킹
        chunks = self.chunk_documents(documents)
        
        # PGVector에 저장
        vectorstore = PGVector.from_documents(
            embedding=self.embeddings,
            documents=chunks,
            collection_name=collection_name,
            connection_string=self.connection_string,
            pre_delete_collection=False  # 기존 컬렉션 유지
        )
        
        return vectorstore
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        collection_name: str = "documents",
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        쿼리와 관련된 문서 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수
            collection_name: 컬렉션 이름
            db: 데이터베이스 세션 (사용 안 함)
        
        Returns:
            관련 문서 리스트 (기존 형식과 호환)
        """
        try:
            # PGVector에서 검색
            vectorstore = PGVector(
                embedding_function=self.embeddings,
                collection_name=collection_name,
                connection_string=self.connection_string
            )
            
            # 유사도 검색
            docs_with_scores = vectorstore.similarity_search_with_score(
                query, 
                k=top_k
            )
            
            # 결과 포맷팅 (기존 RAGService 형식과 호환)
            documents = []
            for doc, score in docs_with_scores:
                # PGVector는 L2 거리를 반환하므로, 유사도로 변환
                # 거리가 작을수록 유사도가 높음: similarity = 1 / (1 + distance)
                similarity = 1.0 / (1.0 + float(score))
                documents.append({
                    "id": None,  # LangChain은 ID를 직접 제공하지 않음
                    "title": doc.metadata.get("title", doc.metadata.get("source", "제목 없음")),
                    "content": doc.page_content[:500],  # 처음 500자만
                    "source": doc.metadata.get("source", "알 수 없음"),
                    "doc_type": doc.metadata.get("doc_type", "unknown"),
                    "similarity": similarity
                })
            
            return documents
        
        except Exception as e:
            print(f"LangChain 검색 오류: {e}")
            # 오류 시 빈 리스트 반환
            return []
    
    async def add_document(
        self,
        title: str,
        content: str,
        source: str = None,
        doc_type: str = None,
        collection_name: str = "documents",
        db: Session = None
    ) -> bool:
        """
        단일 문서를 추가 (기존 인터페이스와 호환)
        
        Args:
            title: 문서 제목
            content: 문서 내용
            source: 출처
            doc_type: 문서 타입
            collection_name: 컬렉션 이름
            db: 데이터베이스 세션 (사용 안 함)
        
        Returns:
            성공 여부
        """
        try:
            # LangChain Document 생성
            doc = LangChainDocument(
                page_content=content,
                metadata={
                    "title": title,
                    "source": source or "unknown",
                    "doc_type": doc_type or "manual"
                }
            )
            
            # 청킹
            chunks = self.chunk_documents([doc])
            
            # PGVector에 저장
            vectorstore = PGVector.from_documents(
                embedding=self.embeddings,
                documents=chunks,
                collection_name=collection_name,
                connection_string=self.connection_string,
                pre_delete_collection=False
            )
            
            return True
        
        except Exception as e:
            print(f"문서 추가 오류: {e}")
            return False

