"""Compose Agent 모듈 - LLM 기반 레이아웃 배치

block_drafts를 분석하여 적절한 레이아웃(row)으로 보고서를 구성합니다.

## 워크플로우
1. block_drafts와 request_context를 LLM에게 전달
2. LLM이 레이아웃 도구(create_row_layout, finalize_report_layout)를 호출
3. 도구 호출 결과를 해석하여 최종 blocks 배열 생성
"""

from __future__ import annotations

import json
import logging
import textwrap
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage

from app.agents.layout_tools import layout_tools

logger = logging.getLogger("uvicorn.error")


# =============================================================================
# 시스템 프롬프트
# =============================================================================

COMPOSE_SYSTEM_PROMPT = textwrap.dedent("""
    당신은 보고서 레이아웃 전문가입니다. 분석된 블록들을 읽기 좋은 보고서로 구성합니다.

    ## 역할
    block_drafts(개별 블록 배열)를 받아서 적절한 레이아웃으로 배치합니다.
    row(가로 배치)를 활용하여 시각적으로 구조화된 보고서를 만듭니다.

    ## 블록 유형
    - markdown: 텍스트 콘텐츠 (제목, 설명, 분석)
    - chart: 시각적 차트 (doughnut, bar, line, pie 등)
    - table: 데이터 표
    - image: 이미지 (포스터, 사진 등)

    ## 레이아웃 규칙

    ### 필수 규칙
    1. **짝 블록 연속 배치**: 차트와 그 설명 마크다운은 반드시 연속 배치
       - 설명 마크다운은 보통 📊, 📈, 📉, 📋, 🔍 이모지로 시작
       - row로 가로 배치: 차트 + 설명을 나란히
       - 또는 그냥 연속 배치 (컨테이너 없이, 세로로 이어짐)

    2. **비율 차트 그룹화**: 연속된 doughnut/pie 차트 2개는 row로 묶어서 비교
    
    3. **이미지 + 설명**: 이미지와 🖼️로 시작하는 설명은 row로 배치
    
    4. **테이블은 단독 배치**: table 블록은 절대 row에 포함하지 않음. 전체 너비를 사용해야 함.
       - 테이블 다음에 오는 설명 마크다운도 단독 배치 (연속으로 세로 배치)

    ### 권장 사항
    - 섹션 제목(##, ###) 마크다운은 단독 배치
    - **테이블(table)은 항상 단독 배치** (row로 묶지 않음, 전체 너비 사용)
    - 도입부 → 핵심 시각화 → 상세 분석 순서 유지

    ## 도구 사용법
    
    1. `create_row_layout`: 블록들을 가로로 배치
       - block_indices: 묶을 블록들의 인덱스 배열
       - gap: 간격 (기본 "16px", 차트 비교는 "24px" 권장)
    
    2. `finalize_report_layout`: 최종 레이아웃 확정 (마지막에 반드시 호출)
       - layout_sequence: 최종 배열 순서
         - 숫자: 개별 블록 인덱스 (순서대로 배치)
         - dict: row 컨테이너 {"type": "row", "indices": [...], "gap": "..."}

    ## 예시

    block_drafts가 다음과 같을 때:
    [0] markdown: "## 방문자 분석"
    [1] chart (doughnut): "연령대별 방문자"
    [2] markdown: "**📊 연령대 분석** 30대가 가장 많습니다"
    [3] chart (doughnut): "성별 방문자"
    [4] markdown: "**📊 성별 분석** 여성이 더 많습니다"
    [5] table: "월별 방문자 현황"
    [6] markdown: "**📋 현황 분석** 10월이 최고였습니다"

    좋은 레이아웃:
    - [0] 제목은 단독
    - [1, 2, 3, 4]는 두 개의 doughnut + 각각의 설명을 row로
    - [5, 6]은 테이블과 설명을 순서대로 (세로 배치)

    finalize_report_layout 호출:
    layout_sequence = [
        0,
        {"type": "row", "indices": [1, 2, 3, 4], "gap": "24px"},
        5,
        6
    ]
""").strip()


# =============================================================================
# 헬퍼 함수
# =============================================================================

def _format_blocks_for_llm(block_drafts: List[dict]) -> str:
    """block_drafts를 LLM이 이해할 수 있는 형식으로 변환합니다."""
    if not block_drafts:
        return "블록이 없습니다."
    
    lines = []
    for i, block in enumerate(block_drafts):
        block_type = block.get("type", "unknown")
        
        if block_type == "markdown":
            content = block.get("content", "")
            # 첫 50자만 표시
            preview = content[:50].replace("\n", " ")
            if len(content) > 50:
                preview += "..."
            lines.append(f"[{i}] markdown: \"{preview}\"")
        
        elif block_type == "chart":
            chart_type = block.get("chartType", "unknown")
            title = block.get("title", "")
            desc = block.get("description", "")[:30] if block.get("description") else ""
            lines.append(f"[{i}] chart ({chart_type}): \"{title}\" - {desc}")
        
        elif block_type == "table":
            title = block.get("title", "")
            row_count = len(block.get("rows", []))
            lines.append(f"[{i}] table: \"{title}\" ({row_count}행)")
        
        elif block_type == "image":
            alt = block.get("alt", "")
            caption = block.get("caption", "")[:30] if block.get("caption") else ""
            lines.append(f"[{i}] image: \"{alt}\" - {caption}")
        
        else:
            lines.append(f"[{i}] {block_type}: (unknown)")
    
    return "\n".join(lines)


def _apply_layout_sequence(block_drafts: List[dict], layout_sequence: List) -> List[dict]:
    """layout_sequence를 적용하여 최종 blocks 배열을 생성합니다."""
    if not layout_sequence:
        return block_drafts.copy()
    
    result = []
    
    for item in layout_sequence:
        if isinstance(item, int):
            # 개별 블록 인덱스
            if 0 <= item < len(block_drafts):
                result.append(block_drafts[item])
        
        elif isinstance(item, dict):
            # row 컨테이너
            container_type = item.get("type", "row")
            indices = item.get("indices", [])
            gap = item.get("gap", "16px")
            
            children = []
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(block_drafts):
                    children.append(block_drafts[idx])
            
            if children:
                result.append({
                    "type": container_type,
                    "gap": gap,
                    "children": children
                })
    
    return result


def _blocks_to_markdown(blocks: List[dict]) -> str:
    """블록 배열을 마크다운 문자열로 변환합니다 (기존 호환용)."""
    result = []
    
    for block in blocks:
        block_type = block.get("type")
        
        if block_type == "markdown":
            result.append(block.get("content", ""))
        
        elif block_type == "chart":
            title = block.get("title", "차트")
            desc = block.get("description", "")
            result.append(f"### {title}\n\n{desc}")
        
        elif block_type == "image":
            url = block.get("url", "")
            alt = block.get("alt", "이미지")
            caption = block.get("caption", "")
            result.append(f'<img src="{url}" alt="{alt}" style="max-width: 100%;" />\n\n*{caption}*')
        
        elif block_type == "table":
            title = block.get("title", "표")
            headers = block.get("headers", [])
            rows = block.get("rows", [])
            desc = block.get("description", "")
            
            md_table = f"### {title}\n\n"
            if headers:
                md_table += "| " + " | ".join(headers) + " |\n"
                md_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            for row in rows:
                md_table += "| " + " | ".join(str(cell) for cell in row) + " |\n"
            if desc:
                md_table += f"\n*{desc}*"
            result.append(md_table)
        
        elif block_type == "row":
            # row 컨테이너의 children 재귀 처리
            children = block.get("children", [])
            child_md = _blocks_to_markdown(children)
            result.append(child_md)
    
    return "\n\n".join(result)


def _fallback_layout(block_drafts: List[dict]) -> List[dict]:
    """LLM 실패 시 기본 룰 기반 레이아웃을 적용합니다."""
    logger.warning("[COMPOSE_AGENT] LLM 레이아웃 실패, 폴백 적용")
    
    if not block_drafts:
        return []
    
    blocks = []
    i = 0
    
    while i < len(block_drafts):
        current = block_drafts[i]
        current_type = current.get("type", "")
        
        # 연속된 doughnut 차트 2개를 row로 묶기
        if (current_type == "chart" and 
            current.get("chartType") == "doughnut" and
            i + 1 < len(block_drafts)):
            
            next_block = block_drafts[i + 1]
            if (next_block.get("type") == "chart" and 
                next_block.get("chartType") == "doughnut"):
                blocks.append({
                    "type": "row",
                    "gap": "24px",
                    "children": [current, next_block]
                })
                i += 2
                continue
        
        blocks.append(current)
        i += 1
    
    return blocks


# =============================================================================
# Compose Agent 생성
# =============================================================================

def create_final_report_compose_agent(llm):
    """
    LLM 기반 Compose Agent를 생성합니다.
    
    워크플로우:
    1. block_drafts를 텍스트로 변환하여 LLM에게 전달
    2. LLM이 레이아웃 도구를 호출하여 배치 결정
    3. finalize_report_layout 결과를 적용하여 최종 blocks 생성
    """
    
    # LLM에 레이아웃 도구 바인딩
    llm_with_tools = llm.bind_tools(layout_tools)

    def compose_report_node(state):
        block_drafts = state.get("block_drafts", [])
        request_context = state.get("request_context", {})
        messages: List = list(state.get("messages", []))
        
        logger.info(f"[COMPOSE_AGENT] 시작 - block_drafts {len(block_drafts)}개")
        
        # 블록이 없으면 빈 결과 반환
        if not block_drafts:
            logger.warning("[COMPOSE_AGENT] block_drafts가 비어있음")
            return {
                "messages": messages,
                "final_report": "",
                "blocks": [],
            }
        
        # === LLM에게 레이아웃 요청 ===
        blocks_text = _format_blocks_for_llm(block_drafts)
        org_name = request_context.get("organization_name", "")
        user_command = request_context.get("user_command", "")
        
        user_message = f"""## 보고서 정보
- 기관: {org_name}
- 요청: {user_command}

## 배치할 블록들 ({len(block_drafts)}개)
{blocks_text}

위 블록들을 적절한 레이아웃으로 구성해주세요.
분석이 끝나면 반드시 `finalize_report_layout` 도구를 호출하여 최종 레이아웃을 확정하세요.
"""
        
        compose_messages = [
            SystemMessage(content=COMPOSE_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        
        layout_sequence = None
        max_iterations = 5
        
        try:
            for iteration in range(max_iterations):
                logger.info(f"[COMPOSE_AGENT] LLM 호출 #{iteration + 1}")
                
                response = llm_with_tools.invoke(compose_messages)
                compose_messages.append(response)
                
                # 도구 호출 확인
                tool_calls = getattr(response, "tool_calls", [])
                
                if not tool_calls:
                    # 도구 호출 없이 응답 종료
                    logger.info("[COMPOSE_AGENT] 도구 호출 없이 응답 완료")
                    break
                
                # 도구 호출 처리
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("args", {})
                    tool_id = tool_call.get("id", "")
                    
                    logger.info(f"[COMPOSE_AGENT] 도구 호출: {tool_name}")
                    
                    if tool_name == "finalize_report_layout":
                        # 최종 레이아웃 확정
                        layout_sequence = tool_args.get("layout_sequence", [])
                        logger.info(f"[COMPOSE_AGENT] 레이아웃 확정: {layout_sequence}")
                        
                        # ToolMessage 추가
                        compose_messages.append(ToolMessage(
                            content=json.dumps({"status": "success", "message": "레이아웃이 확정되었습니다."}),
                            tool_call_id=tool_id
                        ))
                        break
                    
                    elif tool_name in ("create_row_layout", "create_column_layout"):
                        # 레이아웃 도구 호출 확인 (실제 적용은 finalize에서)
                        compose_messages.append(ToolMessage(
                            content=json.dumps({"status": "noted", "args": tool_args}),
                            tool_call_id=tool_id
                        ))
                    
                    else:
                        compose_messages.append(ToolMessage(
                            content=json.dumps({"error": f"Unknown tool: {tool_name}"}),
                            tool_call_id=tool_id
                        ))
                
                # finalize가 호출되었으면 루프 종료
                if layout_sequence is not None:
                    break
            
            # === 레이아웃 적용 ===
            if layout_sequence is not None:
                blocks = _apply_layout_sequence(block_drafts, layout_sequence)
                logger.info(f"[COMPOSE_AGENT] LLM 레이아웃 적용 완료: {len(blocks)}개 블록")
            else:
                # LLM이 finalize를 호출하지 않은 경우 폴백
                blocks = _fallback_layout(block_drafts)
        
        except Exception as e:
            logger.error(f"[COMPOSE_AGENT] LLM 호출 실패: {e}", exc_info=True)
            blocks = _fallback_layout(block_drafts)
        
        # 호환용 마크다운 생성
        final_report = _blocks_to_markdown(blocks)
        
        logger.info(f"[COMPOSE_AGENT] 완료 - blocks {len(blocks)}개")
        
        return {
            "messages": messages,
            "final_report": final_report,
            "blocks": blocks,
        }

    return compose_report_node
