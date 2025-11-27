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

    ## 블록 유형 및 속성
    - **chart/table/image**: 데이터 블록 (id 속성 있음: "block_1", "block_2" 등)
    - **map**: 지도 블록 (시설 위치, 주변 정보 표시)
    - **air_quality**: 대기질 정보 블록 (AQI, 미세먼지 등)
    - **markdown**: 텍스트 블록
      - paired_with="block_X": 해당 블록의 짝 마크다운 (분석 텍스트)
      - role="comprehensive": 총체적 분석 (section 속성으로 구분)
        - section="overview": 개요 (보고서 맨 앞)
        - section="key_findings": 주요 발견 사항
        - section="detailed_analysis": 상세 분석
        - section="implications": 시사점 및 제언 (보고서 맨 끝)
      - 그 외: 독립적인 마크다운 (제목 등)

    ## 레이아웃 규칙

    ### 필수 규칙 (중요!)
    1. **보고서 구조**: 아래 순서로 배치
       - overview (개요) → 맨 앞
       - **map (지도) → 개요 바로 다음 (최우선)** 
       - **air_quality (대기질) → 지도 다음**
       - **접근성 table (title에 "접근성" 포함) → 대기질 다음**
       - key_findings (주요 발견) → 환경정보 다음
       - 데이터 블록 + 짝 마크다운 → 본문
       - detailed_analysis (상세 분석) → 데이터 블록 후
       - implications (시사점) → 맨 끝

    2. **paired_with 연결**: 마크다운의 paired_with가 블록의 id와 같으면 반드시 연속 배치
       - 예: chart(id="block_1") 다음에 markdown(paired_with="block_1")
       - row로 가로 배치하거나 그냥 연속 배치 (세로)

    3. **차트 그룹화 (3~4개 적극 활용)**:
       - doughnut/pie 차트 3~4개 + 각각의 짝 마크다운을 한 row로 묶기
       - 비슷한 주제의 차트는 같은 row에 배치 (예: 연령대별, 성별, 지역별 → 한 row)
       - bar/line 차트도 2~3개씩 row로 그룹핑 가능
       - 차트 + 짝 마크다운 순서: [chart1, markdown1, chart2, markdown2, ...]
    
    4. **테이블은 단독 배치**: table 블록은 row에 포함하지 않음 (전체 너비 사용)
    
    5. **지도/대기질/접근성 블록**: 단독 배치 (전체 너비), 상단 환경정보 영역에 연속 배치

    ## 도구 사용법
    
    1. `create_row_layout`: 블록들을 가로로 배치
       - block_indices: 묶을 블록들의 인덱스 배열
       - gap: 간격 (기본 "16px")
    
    2. `finalize_report_layout`: 최종 레이아웃 확정 (마지막에 반드시 호출)
       - layout_sequence: 최종 배열 순서

    ## 예시

    block_drafts:
    [0] chart (id=block_1, doughnut): "연령대별 방문자"
    [1] chart (id=block_2, doughnut): "성별 방문자"
    [2] chart (id=block_3, doughnut): "지역별 방문자"
    [3] markdown (paired_with=block_1): "**분석 결과** 30대가..."
    [4] markdown (paired_with=block_2): "**분석 결과** 여성이..."
    [5] markdown (paired_with=block_3): "**분석 결과** 서울이..."
    [6] markdown (role=comprehensive, section=overview): "## 개요..."
    [7] markdown (role=comprehensive, section=key_findings): "## 주요 발견..."
    [8] markdown (role=comprehensive, section=implications): "## 시사점..."
    [9] map (id=block_4): "시설 위치"
    [10] air_quality (id=block_5): "대기질 정보"
    [11] table (id=block_6): "접근성 정보"
    [12] chart (id=block_7, bar): "월별 방문 추이"
    [13] markdown (paired_with=block_7): "**분석 결과** 여름 성수기..."

    좋은 레이아웃:
    layout_sequence = [
        6,   // 개요 (맨 앞)
        9,   // 지도 (최우선)
        10,  // 대기질
        11,  // 접근성 테이블
        7,   // 주요 발견
        {"type": "row", "indices": [0, 3, 1, 4, 2, 5], "gap": "20px"},  // 도넛 3개 + 짝 마크다운
        12, 13,  // 막대 차트 + 짝 (단독)
        8    // 시사점 (맨 끝)
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
        block_id = block.get("id", "")
        
        if block_type == "markdown":
            content = block.get("content", "")
            role = block.get("role", "")
            section = block.get("section", "")
            paired_with = block.get("paired_with", "")
            
            # 첫 40자만 표시
            preview = content[:40].replace("\n", " ")
            if len(content) > 40:
                preview += "..."
            
            # role, section, paired_with 정보 추가
            attrs = []
            if role:
                attrs.append(f"role={role}")
            if section:
                attrs.append(f"section={section}")
            if paired_with:
                attrs.append(f"paired_with={paired_with}")
            attr_str = f" ({', '.join(attrs)})" if attrs else ""
            
            lines.append(f"[{i}] markdown{attr_str}: \"{preview}\"")
        
        elif block_type == "chart":
            chart_type = block.get("chartType", "unknown")
            title = block.get("title", "")
            id_str = f", id={block_id}" if block_id else ""
            lines.append(f"[{i}] chart ({chart_type}{id_str}): \"{title}\"")
        
        elif block_type == "table":
            title = block.get("title", "")
            row_count = len(block.get("rows", []))
            id_str = f", id={block_id}" if block_id else ""
            lines.append(f"[{i}] table{id_str}: \"{title}\" ({row_count}행)")
        
        elif block_type == "image":
            alt = block.get("alt", "")
            id_str = f", id={block_id}" if block_id else ""
            lines.append(f"[{i}] image{id_str}: \"{alt}\"")
        
        elif block_type == "map":
            title = block.get("title", "")
            markers_count = len(block.get("markers", []))
            id_str = f", id={block_id}" if block_id else ""
            lines.append(f"[{i}] map{id_str}: \"{title}\" (마커 {markers_count}개)")
        
        elif block_type == "air_quality":
            title = block.get("title", "")
            aqi = block.get("aqi", 0)
            category = block.get("category", "")
            id_str = f", id={block_id}" if block_id else ""
            lines.append(f"[{i}] air_quality{id_str}: \"{title}\" (AQI {aqi}, {category})")
        
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
        
        elif block_type == "map":
            title = block.get("title", "지도")
            desc = block.get("description", "")
            center = block.get("center", {})
            markers = block.get("markers", [])
            md = f"### {title}\n\n"
            md += f"위치: ({center.get('lat', 0):.4f}, {center.get('lng', 0):.4f})\n"
            if markers:
                md += f"표시된 장소: {len(markers)}개\n"
            if desc:
                md += f"\n{desc}"
            result.append(md)
        
        elif block_type == "air_quality":
            title = block.get("title", "대기질")
            aqi = block.get("aqi", 0)
            category = block.get("category", "")
            pollutants = block.get("pollutants", {})
            recommendation = block.get("recommendation", "")
            md = f"### {title}\n\n"
            md += f"- AQI: {aqi} ({category})\n"
            if pollutants.get("pm25"):
                md += f"- PM2.5: {pollutants['pm25']} µg/m³\n"
            if pollutants.get("pm10"):
                md += f"- PM10: {pollutants['pm10']} µg/m³\n"
            if recommendation:
                md += f"\n{recommendation}"
            result.append(md)
        
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
