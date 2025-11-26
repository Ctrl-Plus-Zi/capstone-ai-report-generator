"""Server-Driven Report UI를 위한 블록 스키마 정의

이 모듈은 보고서를 구성하는 다양한 블록 타입들을 정의합니다.
프론트엔드에서는 이 블록 배열을 받아 그대로 렌더링합니다.
"""

from datetime import datetime
from typing import Union, Literal, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# 기본 블록 타입들
# =============================================================================

class MarkdownBlock(BaseModel):
    """마크다운 텍스트 블록"""
    type: Literal["markdown"] = "markdown"
    content: str = Field(..., description="마크다운 형식의 텍스트 내용")


class ChartData(BaseModel):
    """차트 데이터 구조"""
    labels: List[str] = Field(..., description="데이터 라벨 배열")
    values: List[float] = Field(..., description="데이터 값 배열")


class ChartBlock(BaseModel):
    """Chart.js 차트 블록"""
    type: Literal["chart"] = "chart"
    chartType: Literal["doughnut", "bar", "line", "pie", "radar", "polarArea"] = Field(
        ..., description="차트 유형"
    )
    title: str = Field(..., description="차트 제목")
    data: ChartData = Field(..., description="차트 데이터")
    description: Optional[str] = Field("", description="차트 설명")


class ImageBlock(BaseModel):
    """이미지 블록"""
    type: Literal["image"] = "image"
    url: str = Field(..., description="이미지 URL")
    alt: str = Field(..., description="대체 텍스트")
    caption: Optional[str] = Field("", description="이미지 캡션")


class TableBlock(BaseModel):
    """표 블록"""
    type: Literal["table"] = "table"
    title: str = Field(..., description="표 제목")
    headers: List[str] = Field(..., description="열 헤더 배열")
    rows: List[List[str]] = Field(..., description="행 데이터 2차원 배열")
    description: Optional[str] = Field("", description="표 설명")


# =============================================================================
# 컨테이너 블록
# =============================================================================

# 컨텐츠 블록 (row의 children으로 사용 가능한 블록들)
ContentBlock = Union[MarkdownBlock, ChartBlock, ImageBlock, TableBlock]


class RowBlock(BaseModel):
    """가로 배치 컨테이너 블록"""
    type: Literal["row"] = "row"
    gap: Optional[str] = Field("16px", description="자식 요소 간 간격")
    children: List[ContentBlock] = Field(..., description="자식 블록 배열")


# =============================================================================
# 블록 유니온 타입
# =============================================================================

# 모든 블록 타입의 유니온
Block = Union[MarkdownBlock, ChartBlock, ImageBlock, TableBlock, RowBlock]


# =============================================================================
# API 응답 스키마
# =============================================================================

class ReportBlocksResponse(BaseModel):
    """Server-Driven UI 보고서 응답"""
    report_id: str = Field(..., description="보고서 고유 ID")
    title: str = Field(..., description="보고서 제목")
    created_at: datetime = Field(..., description="생성 시각")
    blocks: List[Block] = Field(..., description="보고서 블록 배열")
    
    # 기존 호환용 필드
    final_report: Optional[str] = Field(None, description="기존 호환용 마크다운 보고서")


class BlockDrafts(BaseModel):
    """Analyse Agent 출력용 블록 초안"""
    block_drafts: List[ContentBlock] = Field(..., description="블록 초안 배열 (row 미포함)")


# =============================================================================
# 유틸리티 함수
# =============================================================================

def create_markdown_block(content: str) -> dict:
    """마크다운 블록 생성 헬퍼"""
    return {"type": "markdown", "content": content}


def create_chart_block(
    chart_type: str,
    title: str,
    labels: List[str],
    values: List[float],
    description: str = ""
) -> dict:
    """차트 블록 생성 헬퍼"""
    return {
        "type": "chart",
        "chartType": chart_type,
        "title": title,
        "data": {"labels": labels, "values": values},
        "description": description
    }


def create_table_block(
    title: str,
    headers: List[str],
    rows: List[List[str]],
    description: str = ""
) -> dict:
    """테이블 블록 생성 헬퍼"""
    return {
        "type": "table",
        "title": title,
        "headers": headers,
        "rows": rows,
        "description": description
    }


def create_image_block(url: str, alt: str, caption: str = "") -> dict:
    """이미지 블록 생성 헬퍼"""
    return {"type": "image", "url": url, "alt": alt, "caption": caption}


def create_row_block(children: List[dict], gap: str = "16px") -> dict:
    """Row 컨테이너 블록 생성 헬퍼"""
    return {"type": "row", "gap": gap, "children": children}

