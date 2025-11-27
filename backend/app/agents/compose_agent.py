from __future__ import annotations

import json
import logging
import textwrap
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")


def _arrange_blocks_with_layout(block_drafts: List[dict]) -> List[dict]:
    """블록 초안에 레이아웃(row 컨테이너)을 적용합니다.
    
    규칙:
    1. 연속된 doughnut 차트 2개는 row로 묶기
    2. 이미지 + 마크다운은 row로 묶기
    3. 테이블은 단독 배치
    4. 나머지는 순서 유지
    """
    if not block_drafts:
        return []
    
    blocks = []
    i = 0
    
    while i < len(block_drafts):
        current = block_drafts[i]
        
        # 연속된 doughnut 차트 2개를 row로 묶기
        if (current.get("type") == "chart" and 
            current.get("chartType") == "doughnut" and
            i + 1 < len(block_drafts)):
            next_block = block_drafts[i + 1]
            if (next_block.get("type") == "chart" and 
                next_block.get("chartType") == "doughnut"):
                blocks.append({
                    "type": "row",
                    "gap": "16px",
                    "children": [current, next_block]
                })
                i += 2
                continue
        
        # 이미지 + 마크다운을 row로 묶기
        if (current.get("type") == "image" and
            i + 1 < len(block_drafts)):
            next_block = block_drafts[i + 1]
            if next_block.get("type") == "markdown":
                blocks.append({
                    "type": "row",
                    "gap": "16px",
                    "children": [current, next_block]
                })
                i += 2
                continue
        
        # 그 외는 그대로 추가
        blocks.append(current)
        i += 1
    
    return blocks


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
            
            # 마크다운 테이블 생성
            md_table = f"### {title}\n\n"
            if headers:
                md_table += "| " + " | ".join(headers) + " |\n"
                md_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            for row in rows:
                md_table += "| " + " | ".join(row) + " |\n"
            if desc:
                md_table += f"\n*{desc}*"
            result.append(md_table)
        
        elif block_type == "row":
            # row의 children을 재귀 처리
            children = block.get("children", [])
            child_md = _blocks_to_markdown(children)
            result.append(child_md)
    
    return "\n\n".join(result)


def create_final_report_compose_agent(llm):
    """
    Compose Agent: 블록 레이아웃 적용 및 마크다운 변환
    
    워크플로우:
    1. block_drafts가 있으면 → 레이아웃만 적용 (LLM 호출 없음)
    2. block_drafts가 없으면 → 기존 방식 (LLM 호출)
    """

    def compose_report_node(state):
        request_context = state.get("request_context", {})
        block_drafts = state.get("block_drafts", [])
        messages: List = list(state.get("messages", []))
        
        org_name = request_context.get("organization_name", "문화시설")
        
        # === Server-Driven UI: block_drafts가 있으면 LLM 호출 생략 ===
        if block_drafts:
            logger.info(f"[COMPOSE_AGENT] block_drafts {len(block_drafts)}개 → 레이아웃 적용 (LLM 생략)")
            
            # 블록 레이아웃 적용
            blocks = _arrange_blocks_with_layout(block_drafts)
            
            # 호환용 마크다운 생성
            final_report = _blocks_to_markdown(blocks)
            
            logger.info(f"[COMPOSE_AGENT] blocks 생성 완료: {len(blocks)}개 (원본 {len(block_drafts)}개)")
            
            return {
                "messages": messages,
                "final_report": final_report,
                "compose_prompt": "[블록 기반 - LLM 호출 생략]",
                "blocks": blocks,
            }
        
        # === Fallback: block_drafts 없으면 기존 LLM 방식 ===
        logger.info("[COMPOSE_AGENT] block_drafts 없음 → LLM 호출")
        
        analysis_outline = state.get("analysis_outline", "")
        analysis_findings = state.get("analysis_findings", "")
        research_notes = state.get("research_notes", "")
        latest_performance_image = state.get("latest_performance_image", "")
        report_type = request_context.get("report_type", "user")
        
        # 프롬프트 생성
        prompt = _build_fallback_prompt(
            request_context=request_context,
            analysis_outline=analysis_outline,
            analysis_findings=analysis_findings,
            research_notes=research_notes,
            latest_performance_image=latest_performance_image,
            report_type=report_type
        )

        response = llm.invoke(prompt)
        messages.append(response)
        final_report = response.content.strip() if response else f"# {org_name} 보고서\n\n보고서 생성에 실패했습니다."

        return {
            "messages": messages,
            "final_report": final_report,
            "compose_prompt": prompt,
            "blocks": [],  # 블록 없음
        }

    return compose_report_node


def _build_fallback_prompt(
    request_context: dict,
    analysis_outline: str,
    analysis_findings: str,
    research_notes: str,
    latest_performance_image: str,
    report_type: str
) -> str:
    """block_drafts가 없을 때 사용하는 LLM 프롬프트 (Fallback)"""
    
    org_name = request_context.get("organization_name", "")
    
    if report_type == "operator":
        role = "문화시설 데이터 분석 전문가"
        audience = "운영진과 경영진"
    else:
        role = "문화시설 안내 전문가"
        audience = "일반 이용자"
    
    # 이미지 섹션
    image_section = ""
    if latest_performance_image:
        image_section = f"\n이미지 URL: {latest_performance_image}\n"
    
    request_context_str = json.dumps(request_context, ensure_ascii=False, indent=2)
    
    return textwrap.dedent(f"""
        당신은 {role}입니다.
        
        # 요청 정보
        {request_context_str}
        
        # 분석 개요
        {analysis_outline}
        
        # 핵심 분석 결과
        {analysis_findings}
        
        # 조사 메모
        {research_notes}
        {image_section}
        
        위 정보를 바탕으로 {audience}를 위한 {org_name} 보고서를 마크다운 형식으로 작성하세요.
        코드 블록(```)으로 감싸지 말고 바로 마크다운으로 작성하세요.
    """).strip()
