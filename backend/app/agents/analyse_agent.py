"""분석 에이전트 모듈

수집된 데이터를 분석하고 Server-Driven UI 블록을 생성합니다.

## 핵심 철학
- 에이전트에게 범용 도구를 제공하고, 프롬프트로 제어
- 하드코딩된 변환 로직 없이 LLM이 직접 블록 생성 도구 호출

## 워크플로우
1. 보고서 타입에 따른 프롬프트 분기
2. research_payload 데이터를 LLM에게 전달
3. LLM이 범용 블록 도구(chart, table, markdown, image)를 직접 호출
4. 생성된 블록들을 수집하여 block_drafts 반환
"""

from __future__ import annotations

import json
import logging
import textwrap
from datetime import datetime
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agents.block_tools import (
    create_markdown_block,
    create_chart_block,
    create_table_block,
    create_image_block,
    block_tools,
)

logger = logging.getLogger("uvicorn.error")


# =============================================================================
# JSON 직렬화 헬퍼
# =============================================================================

def _json_serial(obj):
    """JSON 직렬화 헬퍼 (datetime 처리)"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# =============================================================================
# 데이터 요약 및 준비
# =============================================================================

def _prepare_data_for_analysis(research_payload: List[dict]) -> str:
    """
    research_payload를 LLM 분석용 문자열로 변환합니다.
    
    각 데이터의 핵심 정보와 실제 값을 포함하여 LLM이 차트/테이블을 만들 수 있도록 합니다.
    수집 이유(reasoning)도 포함하여 데이터의 맥락을 제공합니다.
    """
    if not research_payload:
        return "수집된 데이터가 없습니다."
    
    sections = []
    
    for item in research_payload:
        tool_name = item.get("tool", "unknown")
        count = item.get("count", 0)
        data = item.get("data", []) or item.get("sample", [])
        stats = item.get("stats", {})
        reasoning = item.get("reasoning", "")  # 수집 이유
        
        section = f"### {tool_name} ({count}개 레코드)\n"
        
        # 수집 이유가 있으면 표시
        if reasoning:
            section += f"**수집 이유:** {reasoning}\n\n"
        
        # 계산된 통계가 있으면 우선 사용 (이미 가공된 데이터)
        if stats:
            section += "**사전 계산된 통계:**\n"
            section += f"```json\n{json.dumps(stats, ensure_ascii=False, indent=2, default=_json_serial)}\n```\n"
        
        # 원본 데이터 샘플 (최대 3개)
        if data and isinstance(data, list):
            sample_data = data[:3]
            section += f"**데이터 샘플 ({min(3, len(data))}개):**\n"
            section += f"```json\n{json.dumps(sample_data, ensure_ascii=False, indent=2, default=_json_serial)}\n```\n"
        
        sections.append(section)
    
    return "\n".join(sections)


def _get_calculated_stats(research_payload: List[dict]) -> tuple[dict, dict]:
    """research_payload에서 calculated_stats와 block_configs 추출"""
    for item in research_payload:
        if item.get("tool") == "calculated_stats":
            stats = item.get("stats", {})
            block_configs = item.get("block_configs", {})
            return stats, block_configs
    return {}, {}


def _create_blocks_from_calculated_stats(
    calculated_stats: dict,
    block_configs: dict = None
) -> List[dict]:
    """
    사전 계산된 통계(calculated_stats)에서 직접 블록을 생성합니다.
    
    search_agent/query_executor에서 이미 계산된 통계이므로
    LLM 호출 없이 바로 블록으로 변환합니다.
    인사이트는 블록의 description 속성에 포함됩니다.
    
    Args:
        calculated_stats: 계산된 통계 딕셔너리
        block_configs: 번들별 블록 설정 (query_bundles.json에서 로드)
    
    Returns:
        생성된 블록 목록 (각 블록에 description으로 인사이트 포함)
    """
    blocks = []
    block_configs = block_configs or {}
    
    # 리뷰 통계 → 평점 분포 차트
    if "review_stats" in calculated_stats:
        stats = calculated_stats["review_stats"]
        distribution = stats.get("rating_distribution", {})
        summary = stats.get("summary", "")
        
        # 블록 설정 가져오기 (있으면 사용, 없으면 기본값)
        review_config = block_configs.get("리뷰", {})
        chart_type = review_config.get("type", "bar")
        title = review_config.get("title", "리뷰 평점 분포")
        purpose = review_config.get("purpose", "")
        
        if distribution:
            labels = ["5점", "4점", "3점", "2점", "1점"]
            values = [
                distribution.get("5점", {}).get("count", 0),
                distribution.get("4점", {}).get("count", 0),
                distribution.get("3점", {}).get("count", 0),
                distribution.get("2점", {}).get("count", 0),
                distribution.get("1점", {}).get("count", 0),
            ]
            
            blocks.append({
                "type": "chart",
                "chartType": chart_type,
                "title": title,
                "data": {"labels": labels, "values": values},
                "description": summary
            })
            logger.info(f"[ANALYSE_AGENT] 사전 계산 통계 → 리뷰 평점 차트 생성 (type={chart_type})")
    
    # 인구통계 → 연령대/성별 차트
    if "demographics_stats" in calculated_stats:
        stats = calculated_stats["demographics_stats"]
        summary = stats.get("summary", "")
        
        # 블록 설정 가져오기
        demo_config = block_configs.get("인구통계", {})
        chart_type = demo_config.get("type", "doughnut")
        split = demo_config.get("split", ["age", "gender"])
        
        if stats.get("has_data"):
            # 연령대 분포
            if "age" in split:
                age_dist = stats.get("age_distribution", {})
                if age_dist:
                    blocks.append({
                        "type": "chart",
                        "chartType": chart_type,
                        "title": "연령대별 방문자 분포",
                        "data": {
                            "labels": list(age_dist.keys()),
                            "values": list(age_dist.values())
                        },
                        "description": summary
                    })
                    logger.info(f"[ANALYSE_AGENT] 사전 계산 통계 → 연령대 차트 생성 (type={chart_type})")
            
            # 성별 분포
            if "gender" in split:
                gender_dist = stats.get("gender_distribution", {})
                if gender_dist:
                    # 성별 인사이트 생성
                    male_pct = gender_dist.get("남성", 0)
                    female_pct = gender_dist.get("여성", 0)
                    if male_pct > female_pct:
                        gender_insight = f"남성 방문자({male_pct}%)가 여성({female_pct}%)보다 많습니다."
                    elif female_pct > male_pct:
                        gender_insight = f"여성 방문자({female_pct}%)가 남성({male_pct}%)보다 많습니다."
                    else:
                        gender_insight = f"남녀 방문자 비율이 비슷합니다 ({male_pct}%)."
                    
                    blocks.append({
                        "type": "chart",
                        "chartType": chart_type,
                        "title": "성별 방문자 분포",
                        "data": {
                            "labels": list(gender_dist.keys()),
                            "values": list(gender_dist.values())
                        },
                        "description": gender_insight
                    })
                    logger.info(f"[ANALYSE_AGENT] 사전 계산 통계 → 성별 차트 생성 (type={chart_type})")
    
    return blocks


def _assign_block_ids(blocks: List[dict]) -> List[dict]:
    """
    각 데이터 블록에 고유 id를 부여합니다.
    
    Args:
        blocks: 데이터 블록 배열
    
    Returns:
        id가 부여된 블록 배열
    """
    result = []
    block_counter = 1
    
    for block in blocks:
        block_copy = block.copy()
        block_type = block.get("type", "")
        
        # 데이터 블록(chart, table, image)에만 id 부여
        if block_type in ("chart", "table", "image"):
            block_copy["id"] = f"block_{block_counter}"
            block_counter += 1
        
        result.append(block_copy)
    
    return result


def _generate_paired_markdowns(
    llm,
    blocks: List[dict],
    report_type: str = "user",
    org_name: str = "",
    report_topic: str = ""
) -> List[dict]:
    """
    각 데이터 블록에 대한 짝 마크다운 블록을 생성합니다.
    
    Args:
        llm: LangChain LLM 인스턴스 (외부에서 주입)
        blocks: id가 부여된 데이터 블록 배열
        report_type: "user" 또는 "operator"
        org_name: 기관명
        report_topic: 보고서 주제
    
    Returns:
        짝 마크다운 블록 배열: [{"type": "markdown", "paired_with": "block_1", "content": "..."}]
    """
    # id가 있는 블록만 추출
    data_blocks = [b for b in blocks if b.get("id")]
    
    if not data_blocks:
        return []
    
    # 블록 정보 텍스트 생성
    blocks_text = ""
    for b in data_blocks:
        block_id = b.get("id", "")
        block_type = b.get("type", "")
        title = b.get("title", "") or b.get("alt", "")
        description = b.get("description", "") or b.get("caption", "")
        chart_type = b.get("chartType", "")
        data_summary = _summarize_block_data(b)
        
        blocks_text += f"""
### {block_id}: {title}
- 타입: {block_type}{f" ({chart_type})" if chart_type else ""}
- 기존 설명: {description if description else "(없음)"}
- {data_summary}
"""
    
    tone = "전문적이고 격식 있는 어조" if report_type == "operator" else "친근한 어조"
    
    prompt = f"""# 역할
'{org_name}' 데이터 분석가. {tone}로 작성.

# 보고서 주제
{report_topic}

# 데이터 블록들
{blocks_text}

# 작업
각 블록에 대한 짝 마크다운을 생성하세요. (블록당 1개)

# 출력 형식 (JSON 배열만 출력)
[
  {{"type": "markdown", "paired_with": "block_1", "content": "**분석 결과**\\n\\n데이터 해석 내용을 2-3문장으로 작성합니다."}},
  {{"type": "markdown", "paired_with": "block_2", "content": "**분석 결과**\\n\\n데이터 해석 내용을 2-3문장으로 작성합니다."}}
]

# 규칙
- paired_with: 해당 블록의 id
- content: 수치를 구체적으로 인용한 분석 (2-3문장)
- 기존 설명이 있으면 참고하되, 더 풍부하게 작성
- 이모티콘 사용 금지
"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content
        
        # JSON 파싱
        json_match = response_text.find("[")
        json_end = response_text.rfind("]") + 1
        if json_match != -1 and json_end > json_match:
            json_str = response_text[json_match:json_end]
            paired_markdowns = json.loads(json_str)
            logger.info(f"[ANALYSE_AGENT] 짝 마크다운 {len(paired_markdowns)}개 생성")
            return paired_markdowns
        else:
            logger.warning("[ANALYSE_AGENT] 짝 마크다운 JSON 파싱 실패")
            return []
        
    except Exception as e:
        logger.error(f"[ANALYSE_AGENT] 짝 마크다운 생성 실패: {e}")
        return []


def _summarize_block_data(block: dict) -> str:
    """블록 데이터를 간략히 요약"""
    block_type = block.get("type", "")
    
    if block_type == "chart":
        data = block.get("data", {})
        labels = data.get("labels", [])
        values = data.get("values", [])
        # 전체 데이터 포함
        pairs = [f"{l}: {v}" for l, v in zip(labels, values)]
        return f"데이터: {', '.join(pairs)}"
    elif block_type == "table":
        headers = block.get("headers", [])
        rows = block.get("rows", [])
        row_count = len(rows)
        sample = rows[:2] if rows else []
        return f"컬럼: {headers}, 행 수: {row_count}, 샘플: {sample}"
    elif block_type == "image":
        return f"이미지: {block.get('alt', '')}, 캡션: {block.get('caption', '')}"
    return ""


def _generate_comprehensive_analysis(
    llm,
    data_blocks: List[dict],
    paired_markdowns: List[dict],
    report_type: str = "user",
    org_name: str = "",
    report_topic: str = ""
) -> List[dict]:
    """
    총체적 분석을 수행하여 여러 문단의 마크다운 블록을 생성합니다.
    
    Args:
        llm: LangChain LLM 인스턴스
        data_blocks: id가 부여된 데이터 블록들 (chart, table, image)
        paired_markdowns: 짝 마크다운 블록들
        report_type: "user" 또는 "operator"
        org_name: 기관명
        report_topic: 보고서 주제
    
    Returns:
        총체적 분석 마크다운 블록 배열 (role="comprehensive" 속성 포함)
    """
    if not data_blocks:
        return []
    
    # === 컨텍스트 수집 ===
    
    # 1. 데이터 블록 정보 수집
    blocks_context = ""
    for block in data_blocks:
        block_id = block.get("id", "")
        block_type = block.get("type", "")
        title = block.get("title", "") or block.get("alt", "")
        description = block.get("description", "") or block.get("caption", "")
        chart_type = block.get("chartType", "")
        data_summary = _summarize_block_data(block)
        
        blocks_context += f"""
[{block_id}] {title}
- 유형: {block_type}{f" ({chart_type})" if chart_type else ""}
- 기존 설명: {description if description else "(없음)"}
- {data_summary}
"""
    
    # 2. 짝 마크다운 내용 수집
    paired_context = ""
    for md in paired_markdowns:
        paired_with = md.get("paired_with", "")
        content = md.get("content", "")
        paired_context += f"""
[{paired_with}에 대한 분석]
{content}
"""
    
    # 3. 보고서 어조 설정
    tone = "전문적이고 격식 있는 어조로 작성하세요. 운영자가 의사결정에 활용할 수 있도록 구체적인 수치와 시사점을 포함하세요." if report_type == "operator" else "친근하고 이해하기 쉬운 어조로 작성하세요. 일반 방문자가 이해할 수 있도록 설명하세요."
    
    # === 프롬프트 구성 ===
    prompt = f"""# 역할
당신은 '{org_name}' 데이터 분석 전문가입니다.
{tone}

# 보고서 주제
{report_topic}

# 분석 대상 데이터
{blocks_context}

# 개별 분석 내용
{paired_context}

# 작업
위 데이터와 개별 분석을 종합하여 총체적 분석 보고서를 작성하세요.
아래 템플릿에 맞춰 각 섹션을 작성하고, JSON 배열로 출력하세요.

# 출력 형식 (JSON 배열만 출력)
[
  {{"section": "overview", "content": "## 개요\\n\\n(보고서의 배경과 목적, 분석 범위를 1-2문단으로 설명)"}},
  {{"section": "key_findings", "content": "## 주요 발견 사항\\n\\n(가장 중요한 인사이트 3-4개를 글머리 기호로 정리)"}},
  {{"section": "detailed_analysis", "content": "## 상세 분석\\n\\n(데이터 간 관계, 패턴, 트렌드를 2-3문단으로 심층 분석)"}},
  {{"section": "implications", "content": "## 시사점 및 제언\\n\\n(분석 결과의 의미와 향후 방향성을 1-2문단으로 제시)"}}
]

# 규칙
1. 이모티콘 사용 금지
2. 구체적인 수치를 반드시 인용
3. 각 섹션은 독립적으로 읽혀도 이해 가능해야 함
4. 마크다운 형식 사용 (##, -, ** 등)
5. 추측이나 가정 없이 데이터에 기반하여 작성
"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content
        
        # JSON 파싱
        json_match = response_text.find("[")
        json_end = response_text.rfind("]") + 1
        
        if json_match != -1 and json_end > json_match:
            json_str = response_text[json_match:json_end]
            sections = json.loads(json_str)
            
            # 각 섹션을 마크다운 블록으로 변환
            comprehensive_blocks = []
            for section in sections:
                section_name = section.get("section", "")
                content = section.get("content", "")
                
                if content:
                    comprehensive_blocks.append({
                        "type": "markdown",
                        "role": "comprehensive",
                        "section": section_name,
                        "content": content
                    })
            
            logger.info(f"[ANALYSE_AGENT] 총체적 분석 {len(comprehensive_blocks)}개 섹션 생성")
            return comprehensive_blocks
        else:
            logger.warning("[ANALYSE_AGENT] 총체적 분석 JSON 파싱 실패")
            return []
        
    except Exception as e:
        logger.error(f"[ANALYSE_AGENT] 총체적 분석 생성 실패: {e}")
        return []


# =============================================================================
# 시스템 프롬프트 생성
# =============================================================================

def _build_analysis_prompt(
    report_type: str,
    org_name: str,
    report_topic: str,
    data_text: str,
    latest_image: str = "",
    block_configs: dict = None
) -> str:
    """분석 및 블록 생성을 위한 시스템 프롬프트 생성"""
    
    # 보고서 타입별 지침
    if report_type == "operator":
        audience = "운영자/관리자"
        focus = """
        - 데이터 기반의 객관적 분석 (수치와 비율 강조)
        - 방문자 트렌드 및 패턴 분석
        - 타겟층 분석 (연령대별, 성별 방문자 통계)
        - 리뷰 평점 분포와 만족도 분석
        """
    else:
        audience = "일반 이용자"
        focus = """
        - 시설 소개 및 특징
        - 방문 팁과 추천 정보
        - 현재 진행 중인 전시/공연 정보
        - 다른 방문객들의 평가 요약
        """
    
    image_instruction = ""
    if latest_image:
        image_instruction = f"""
## 이미지 정보
최근 전시/공연 이미지 URL: {latest_image}
→ create_image_block 도구로 이미지 블록을 생성하세요.
"""
    
    # 번들별 생성해야 할 블록 목록
    bundle_instructions = ""
    if block_configs:
        bundle_lines = []
        for bundle_name, config in block_configs.items():
            purpose = config.get("purpose", "")
            block_type = config.get("type", "llm")
            title = config.get("title", "")
            
            if purpose:
                instruction = f"- **{bundle_name}**: {purpose}"
                if block_type != "llm" and title:
                    instruction += f" → {block_type} 차트로 '{title}' 생성"
                bundle_lines.append(instruction)
        
        if bundle_lines:
            bundle_instructions = f"""
## 생성해야 할 블록 목록 (필수!)
다음 데이터 분석을 수행하고 각각 블록을 생성하세요:

{chr(10).join(bundle_lines)}

**중요: 위 목록의 모든 항목에 대해 블록을 생성해야 합니다.**
"""
    
    return textwrap.dedent(f"""
        # 역할
        당신은 {org_name}에 대한 데이터 분석가입니다.
        수집된 데이터를 분석하고, **범용 블록 생성 도구**를 사용하여 보고서 블록을 직접 생성합니다.
        
        # 보고서 정보
        - 기관명: {org_name}
        - 보고서 주제: {report_topic}
        - 독자: {audience}
        
        # 분석 초점
        {focus}
        
        # 사용 가능한 도구
        
        ## 1. create_chart_block
        차트 블록 생성. 데이터 시각화에 사용.
        - chart_type: "doughnut" (비율), "bar" (비교), "line" (추이), "pie" (구성비)
        - title: 차트 제목
        - labels: 라벨 배열 (예: ["20대", "30대", "40대"])
        - values: 값 배열 (예: [25.5, 35.2, 22.1])
        - description: **자세한 분석 설명** (필수! 3문장 이상)
          - 왜 이 차트 유형을 선택했는지
          - 데이터에서 발견한 핵심 패턴/특징
          - 이 데이터가 의미하는 바 (인사이트)
        
        ## 2. create_table_block
        테이블 블록 생성. 상세 정보 정리에 사용.
        - title: 표 제목
        - headers: 열 헤더 배열
        - rows: 2차원 행 데이터 배열
        - description: **자세한 설명** (2문장 이상, 표가 보여주는 정보 설명)
        
        ## 3. create_markdown_block
        마크다운 텍스트 블록 생성. 설명, 요약, 결론에 사용.
        - content: 마크다운 형식 텍스트
        
        ## 4. create_image_block
        이미지 블록 생성. 전시/공연 포스터에 사용.
        - url: 이미지 URL
        - alt: 대체 텍스트
        - caption: 캡션
        
        {image_instruction}
        
        {bundle_instructions}
        
        # 수집된 데이터
        {data_text}
        
        # 블록 생성 지침
        
        1. **위 "생성해야 할 블록 목록"을 반드시 확인하고 모두 생성**
           - 이미 생성된 블록(주의 표시)은 제외
           - 데이터가 있으면 반드시 해당 차트/테이블 생성
        
        2. **차트/테이블 생성 시 주의**
           - labels와 values 배열 길이가 동일해야 함
           - values는 실제 숫자 (문자열 X)
           - description은 자세하게 작성 (2-3문장)
        
        3. **데이터에서 값 추출하는 법**
           - tmz_cnt_00~tmz_cnt_23 → 0시~23시 방문자 수
           - week_01~week_07 → 월~일 요일별 방문자 수
           - wkdy_rt, wknd_rt → 평일/주말 비율
           - income_01~03 → 저/중/고소득층 비율
           - 각 컬럼명은 purpose에 힌트가 있음
        
        # 시작
        위 데이터를 분석하고, **생성해야 할 블록 목록의 모든 항목**에 대해 도구를 호출하세요.
    """).strip()


# =============================================================================
# 메인: Analyse Agent 노드 생성
# =============================================================================

def create_analyse_agent(tool_llm, summary_llm, toolkit):
    """
    분석 에이전트 노드를 생성합니다.
    
    ## 워크플로우
    1. 보고서 타입에 따른 프롬프트 분기
    2. research_payload를 분석용 텍스트로 변환
    3. LLM이 범용 블록 도구(create_chart_block 등)를 직접 호출
    4. 도구 호출 결과를 block_drafts로 수집
    5. 분석 요약(analysis_findings) 생성
    """
    
    # 사용할 도구들
    tools = block_tools  # [create_markdown_block, create_chart_block, create_table_block, create_image_block]

    def analyse_agent_node(state):
        logger.info("[ANALYSE_AGENT] ====== 시작 ======")

        # === 상태 추출 ===
        request_context = state.get("request_context", {})
        research_payload = state.get("research_payload", [])
        latest_image = state.get("latest_performance_image", "")
        messages = list(state.get("messages", []))
        
        report_type = request_context.get("report_type", "user")
        org_name = request_context.get("organization_name", "해당 시설")
        report_topic = request_context.get("report_topic", "")
        
        logger.info(f"[ANALYSE_AGENT] 기관: {org_name}, 타입: {report_type}")
        logger.info(f"[ANALYSE_AGENT] research_payload: {len(research_payload)}개 항목")
        
        # === 단계 1: 사전 계산된 통계에서 블록 직접 생성 (LLM 스킵) ===
        calculated_stats, block_configs = _get_calculated_stats(research_payload)
        pre_generated_blocks = []
        
        if calculated_stats:
            pre_generated_blocks = _create_blocks_from_calculated_stats(
                calculated_stats, block_configs
            )
            logger.info(f"[ANALYSE_AGENT] 사전 계산 통계에서 {len(pre_generated_blocks)}개 블록 생성")
            if block_configs:
                logger.info(f"[ANALYSE_AGENT] 블록 설정 사용: {list(block_configs.keys())}")
        
        # === 단계 2: 데이터 준비 (LLM용) ===
        data_text = _prepare_data_for_analysis(research_payload)
        
        # === 단계 3: 시스템 프롬프트 생성 ===
        # 사전 생성된 블록 정보를 프롬프트에 포함
        pre_generated_info = ""
        if pre_generated_blocks:
            block_titles = [b.get("title", b.get("type", "")) for b in pre_generated_blocks]
            pre_generated_info = f"\n\n**주의: 다음 블록은 이미 생성되었으므로 다시 만들지 마세요:** {', '.join(block_titles)}"
        
        system_prompt = _build_analysis_prompt(
            report_type=report_type,
            org_name=org_name,
            report_topic=report_topic,
            data_text=data_text + pre_generated_info,
            latest_image=latest_image,
            block_configs=block_configs
        )
        
        # === 단계 4: LLM 호출 (도구 바인딩) ===
        logger.info(f"[ANALYSE_AGENT] LLM 호출 시작 (도구 {len(tools)}개)")
        
        llm_with_tools = tool_llm.bind_tools(tools)
        
        analysis_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="위 데이터를 분석하고 블록 생성 도구를 호출하여 보고서 블록을 만들어주세요.")
        ]
        
        # 첫 번째 응답
        ai_response = llm_with_tools.invoke(analysis_messages)
        analysis_messages.append(ai_response)
        
        # === 단계 5: 도구 호출 처리 및 블록 수집 ===
        llm_generated_blocks = []
        tool_call_count = 0
        max_iterations = 5  # 무한 루프 방지
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 도구 호출이 있는지 확인
            if not hasattr(ai_response, "tool_calls") or not ai_response.tool_calls:
                logger.info(f"[ANALYSE_AGENT] 도구 호출 없음, 반복 종료")
                break
            
            logger.info(f"[ANALYSE_AGENT] 도구 호출 {len(ai_response.tool_calls)}개 발견")
            
            # 각 도구 호출 처리
            for tool_call in ai_response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", "")
                
                logger.info(f"[ANALYSE_AGENT] 도구 호출: {tool_name}")
                
                # 도구 찾기 및 실행
                tool_fn = next((t for t in tools if t.name == tool_name), None)
                
                if tool_fn:
                    try:
                        # 도구 실행
                        block = tool_fn.invoke(tool_args)
                        llm_generated_blocks.append(block)
                        tool_call_count += 1
                        
                        logger.info(f"[ANALYSE_AGENT] 블록 생성 완료: {block.get('type', 'unknown')} - {block.get('title', block.get('content', '')[:30] if block.get('content') else '')}")
                        
                        # 도구 결과 메시지 추가
                        analysis_messages.append(
                            ToolMessage(
                                tool_call_id=tool_id,
                                content=json.dumps(block, ensure_ascii=False, default=_json_serial)
                            )
                        )
                    except Exception as e:
                        logger.error(f"[ANALYSE_AGENT] 도구 실행 실패 ({tool_name}): {e}")
                        analysis_messages.append(
                    ToolMessage(
                                tool_call_id=tool_id,
                                content=json.dumps({"error": str(e)})
                            )
                        )
                else:
                    logger.warning(f"[ANALYSE_AGENT] 알 수 없는 도구: {tool_name}")
                    analysis_messages.append(
                        ToolMessage(
                            tool_call_id=tool_id,
                            content=json.dumps({"error": f"Unknown tool: {tool_name}"})
                        )
                    )
            
            # 다음 응답 요청 (더 많은 도구 호출이 필요한지 확인)
            ai_response = llm_with_tools.invoke(analysis_messages)
            analysis_messages.append(ai_response)
        
        logger.info(f"[ANALYSE_AGENT] LLM 도구 호출 {tool_call_count}회, {len(llm_generated_blocks)}개 블록 생성")
        
        # === 단계 6: 블록 병합 (사전 생성 + LLM 생성) ===
        block_drafts = []
        
        # 사전 생성된 블록 먼저 추가
        block_drafts.extend(pre_generated_blocks)
        
        # LLM 생성 블록 중 중복되지 않는 것만 추가
        pre_generated_titles = {b.get("title", "") for b in pre_generated_blocks}
        for block in llm_generated_blocks:
            block_title = block.get("title", "")
            # 중복 체크: 같은 제목의 차트가 이미 있으면 스킵
            if block_title and block_title in pre_generated_titles:
                logger.info(f"[ANALYSE_AGENT] 중복 블록 스킵: {block_title}")
                continue
            block_drafts.append(block)
        
        logger.info(f"[ANALYSE_AGENT] 최종 블록: 사전생성 {len(pre_generated_blocks)}개 + LLM {len(llm_generated_blocks)}개 → 총 {len(block_drafts)}개")
        
        # === 단계 7: 블록에 고유 id 부여 ===
        block_drafts = _assign_block_ids(block_drafts)
        logger.info(f"[ANALYSE_AGENT] 블록 id 부여 완료")
        
        # === 단계 8: 짝 마크다운 생성 (paired_with로 연결) ===
        paired_markdowns = _generate_paired_markdowns(
            llm=summary_llm,
            blocks=block_drafts,
            report_type=report_type,
            org_name=org_name,
            report_topic=report_topic
        )
        logger.info(f"[ANALYSE_AGENT] 짝 마크다운 {len(paired_markdowns)}개 생성")
        
        # === 단계 9: 총체적 분석 생성 ===
        # 데이터 블록 (id가 있는 블록들)과 짝 마크다운을 기반으로 종합 분석
        data_blocks = [b for b in block_drafts if b.get("id")]
        comprehensive_blocks = _generate_comprehensive_analysis(
            llm=summary_llm,
            data_blocks=data_blocks,
            paired_markdowns=paired_markdowns,
            report_type=report_type,
            org_name=org_name,
            report_topic=report_topic
        )
        logger.info(f"[ANALYSE_AGENT] 총체적 분석 {len(comprehensive_blocks)}개 섹션 생성")
        
        # === 블록 조합: 총체적 분석(앞) + 데이터 블록 + 짝 마크다운 ===
        # Compose Agent가 최종 배치를 결정하지만, 기본 순서 제공
        block_drafts.extend(paired_markdowns)
        block_drafts.extend(comprehensive_blocks)
        logger.info(f"[ANALYSE_AGENT] 전체 블록 조합 완료: {len(block_drafts)}개")
        
        # === 단계 10: Fallback - 블록이 없으면 에러 메시지 ===
        if not block_drafts:
            logger.warning(f"[ANALYSE_AGENT] 블록 생성 실패, fallback 메시지 생성")
            block_drafts = [{
                "type": "markdown",
                "content": f"## {org_name}\n\n데이터 분석 중 문제가 발생했습니다. 수집된 데이터가 없거나 분석에 실패했습니다."
            }]
        
        logger.info(f"[ANALYSE_AGENT] ====== 완료 ======")
        logger.info(f"[ANALYSE_AGENT] 최종 block_drafts: {len(block_drafts)}개 블록")

        return {
            "messages": messages,
            "block_drafts": block_drafts,
        }

    return analyse_agent_node
