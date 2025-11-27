"""레이아웃 도구 모듈

Compose Agent가 블록들을 row 컨테이너로 배치할 때 사용하는 도구입니다.
LLM이 block_drafts를 분석하고 적절한 레이아웃을 결정합니다.
"""

from typing import List, Annotated
from langchain_core.tools import tool


@tool
def create_row_layout(
    block_indices: Annotated[List[int], "가로로 배치할 블록들의 인덱스 배열 (예: [0, 1])"],
    gap: Annotated[str, "블록 간 간격 (예: '16px', '24px')"] = "16px"
) -> dict:
    """블록들을 가로(row)로 나란히 배치합니다.
    
    사용 시점:
    - 비율 차트 2개를 나란히 비교할 때 (doughnut, pie)
    - 이미지와 설명을 나란히 배치할 때
    - 짧은 차트와 간단한 설명을 옆에 배치할 때
    
    예시:
    - [차트, 설명 마크다운] → 가로 배치
    - [doughnut 차트, doughnut 차트] → 나란히 비교
    
    Returns:
        {"action": "row", "indices": [...], "gap": "..."}
    """
    return {
        "action": "row",
        "indices": block_indices,
        "gap": gap
    }


@tool
def finalize_report_layout(
    layout_sequence: Annotated[
        List[int | dict], 
        "최종 블록 배열 순서. 숫자는 개별 블록 인덱스, dict는 row 컨테이너 (예: [0, {'type': 'row', 'indices': [1, 2]}, 3])"
    ]
) -> dict:
    """보고서의 최종 레이아웃 순서를 확정합니다.
    
    이 도구를 마지막에 호출하여 전체 보고서 구조를 완성합니다.
    
    layout_sequence 예시:
    - [0, 1, 2, 3] → 모든 블록을 순서대로 배치
    - [0, {"type": "row", "indices": [1, 2], "gap": "16px"}, 3] → 1,2번을 row로 묶고 나머지는 순서대로
    - [0, {"type": "row", "indices": [1, 2]}, {"type": "row", "indices": [3, 4]}, 5] → 여러 row 그룹
    
    Returns:
        {"action": "finalize", "sequence": [...]}
    """
    return {
        "action": "finalize",
        "sequence": layout_sequence
    }


# 레이아웃 도구 리스트
layout_tools = [
    create_row_layout,
    finalize_report_layout,
]

