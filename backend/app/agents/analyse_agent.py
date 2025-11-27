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
) -> tuple[List[dict], List[str]]:
    """
    사전 계산된 통계(calculated_stats)에서 직접 블록과 인사이트를 생성합니다.
    
    search_agent/query_executor에서 이미 계산된 통계이므로
    LLM 호출 없이 바로 블록으로 변환합니다.
    
    Args:
        calculated_stats: 계산된 통계 딕셔너리
        block_configs: 번들별 블록 설정 (query_bundles.json에서 로드)
    
    Returns:
        (blocks, insights): 생성된 블록 목록과 인사이트 문자열 목록
    """
    blocks = []
    insights = []
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
            
            # 인사이트 추출
            if summary:
                insights.append(f"**리뷰 분석**: {summary}")
            
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
            
            # 인구통계 인사이트 추출
            if summary:
                insights.append(f"**방문자 분석**: {summary}")
    
    return blocks, insights


def _add_analysis_report_markdown(
    blocks: List[dict],
    report_type: str = "user",
    org_name: str = "",
    report_topic: str = ""
) -> List[dict]:
    """
    시스템 프롬프트 + 블록 정보를 기반으로 전체 분석 보고서 마크다운을 생성합니다.
    
    생성된 보고서 마크다운 블록을 맨 앞에 추가하고,
    각 블록 뒤에도 짝 마크다운을 추가합니다.
    """
    from langchain_openai import ChatOpenAI
    
    # 블록 정보 수집
    blocks_info = _collect_block_info(blocks)
    
    if not blocks_info:
        return blocks
    
    # 보고서 타입별 시스템 프롬프트
    if report_type == "operator":
        system_prompt = f"""당신은 '{org_name}'의 문화시설 운영 분석 전문가입니다.

## 역할
- 운영자/관리자를 위한 데이터 기반 분석 보고서 작성
- 운영 개선점과 전략적 인사이트 제시

## 말투
- 전문적이고 격식 있는 보고서 어조
- "~로 나타났습니다", "~을 고려해야 합니다" 등 격식체
- 데이터 수치를 명확히 인용
"""
    else:
        system_prompt = f"""당신은 '{org_name}'의 문화시설 안내 전문가입니다.

## 역할  
- 일반 이용자를 위한 친근하고 유익한 정보 제공
- 방문 계획에 도움이 되는 인사이트 전달

## 말투
- 친근하면서도 신뢰감 있는 어조
- "~네요", "~입니다" 등 부드러운 경어체
- 쉽게 이해할 수 있도록 설명
"""
    
    # 블록 정보를 텍스트로 변환
    blocks_text = _format_blocks_for_prompt(blocks_info)
    
    # LLM 프롬프트 구성: ## 헤더로 문단 구분
    prompt = f"""{system_prompt}

# 보고서 주제
{report_topic}

# 분석 대상 데이터
{blocks_text}

# 작업
위 데이터를 바탕으로 분석 보고서를 작성해주세요.

# 출력 형식 (중요!)
반드시 ## 헤더로 각 문단을 구분하세요:

## 📋 분석 요약
(전체 데이터의 핵심 인사이트 2-3문장)

## 📊 [블록1 제목] 분석
(해당 데이터 분석 2-3문장)

## 📊 [블록2 제목] 분석
(해당 데이터 분석 2-3문장)

... (각 블록마다 ##로 구분)

## 💡 결론
(종합 결론 및 시사점 2-3문장)

# 주의사항
- 반드시 ##로 각 섹션 시작
- 수치를 구체적으로 인용
- 각 블록의 기존 설명 참고
"""
    
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        response = llm.invoke([HumanMessage(content=prompt)])
        report_content = response.content
        
        logger.info(f"[ANALYSE_AGENT] 분석 보고서 마크다운 생성 완료")
        
        # ## 기준으로 분리하여 각각 마크다운 블록 생성
        markdown_blocks = _split_by_headers(report_content)
        
        # 결과: 요약 마크다운들 + 원본 블록들 인터리브 + 결론
        result = _interleave_blocks_and_analyses(blocks, blocks_info, markdown_blocks)
        
        return result
        
    except Exception as e:
        logger.error(f"[ANALYSE_AGENT] 분석 보고서 생성 실패: {e}")
        # 폴백: 원본 블록 그대로 반환
        return blocks


def _collect_block_info(blocks: List[dict], path_prefix: str = "") -> List[dict]:
    """블록들을 순회하며 정보 수집"""
    result = []
    
    for i, block in enumerate(blocks):
        block_type = block.get("type", "")
        
        if block_type == "row":
            result.extend(_collect_block_info(block.get("children", []), f"{path_prefix}{i}.children."))
        elif block_type in ["chart", "table", "image"]:
            result.append({
                "index": str(len(result)),
                "path": f"{path_prefix}{i}",
                "type": block_type,
                "title": block.get("title", "") or block.get("alt", ""),
                "description": block.get("description", "") or block.get("caption", ""),
                "chart_type": block.get("chartType", ""),
                "data_summary": _summarize_block_data(block)
            })
    
    return result


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


def _format_blocks_for_prompt(blocks_info: List[dict]) -> str:
    """블록 정보를 프롬프트용 텍스트로 변환"""
    text = ""
    for info in blocks_info:
        text += f"""
### 블록 {int(info['index']) + 1}: {info['title']}
- 타입: {info['type']} {f"({info['chart_type']})" if info['chart_type'] else ""}
- 기존 설명: {info['description']}
- {info['data_summary']}
"""
    return text


def _split_by_headers(content: str) -> List[dict]:
    """## 헤더 기준으로 마크다운을 분리하여 블록 리스트 생성"""
    blocks = []
    
    # ## 로 분리
    sections = content.split("\n## ")
    
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        
        # 첫 번째가 아니면 ## 복원
        if i > 0:
            section = "## " + section
        elif not section.startswith("##"):
            # 첫 섹션이 ##로 시작하지 않으면 스킵 (프롬프트 반복 등)
            if "##" in section:
                section = "## " + section.split("## ", 1)[1]
            else:
                continue
        
        # 헤더와 내용 분리
        lines = section.split("\n", 1)
        header = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        
        # 헤더에서 타입 추출 (요약/분석/결론)
        block_type = "analysis"
        if "요약" in header:
            block_type = "summary"
        elif "결론" in header:
            block_type = "conclusion"
        
        blocks.append({
            "header": header,
            "body": body,
            "type": block_type,
            "full_content": section
        })
    
    return blocks


def _interleave_blocks_and_analyses(
    data_blocks: List[dict],
    blocks_info: List[dict],
    markdown_sections: List[dict]
) -> List[dict]:
    """데이터 블록과 분석 마크다운을 인터리브하여 최종 결과 생성"""
    result = []
    
    # 요약 섹션들 먼저 추가
    for section in markdown_sections:
        if section["type"] == "summary":
            result.append({
                "type": "markdown",
                "content": section["full_content"]
            })
    
    # 데이터 블록과 해당 분석 마크다운 매칭
    analysis_sections = [s for s in markdown_sections if s["type"] == "analysis"]
    
    for i, data_block in enumerate(data_blocks):
        # 데이터 블록 추가
        result.append(data_block)
        
        # 해당 블록의 분석 마크다운 찾기 (제목 매칭)
        block_title = data_block.get("title", "") or data_block.get("alt", "")
        
        matched_analysis = None
        for analysis in analysis_sections:
            # 헤더에 블록 제목이 포함되어 있으면 매칭
            if block_title and block_title in analysis["header"]:
                matched_analysis = analysis
                break
        
        # 매칭된 분석이 없으면 순서대로 매칭
        if not matched_analysis and i < len(analysis_sections):
            matched_analysis = analysis_sections[i]
        
        if matched_analysis:
            result.append({
                "type": "markdown",
                "content": matched_analysis["full_content"]
            })
            # 사용한 분석은 제거
            if matched_analysis in analysis_sections:
                analysis_sections.remove(matched_analysis)
    
    # 남은 분석 섹션들 추가
    for section in analysis_sections:
        result.append({
            "type": "markdown",
            "content": section["full_content"]
        })
    
    # 결론 섹션들 마지막에 추가
    for section in markdown_sections:
        if section["type"] == "conclusion":
            result.append({
                "type": "markdown",
                "content": section["full_content"]
            })
    
    return result


# =============================================================================
# 시스템 프롬프트 생성
# =============================================================================

def _build_analysis_prompt(
    report_type: str,
    org_name: str,
    report_topic: str,
    data_text: str,
    latest_image: str = ""
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
        
        # 수집된 데이터
        {data_text}
        
        # 블록 생성 지침
        
        1. **데이터 분석 후 적절한 도구 선택**
           - 비율/분포 데이터 → create_chart_block (doughnut 또는 bar)
           - 상세 목록 데이터 → create_table_block
           - 설명/요약 → create_markdown_block
        
        2. **차트/테이블 생성 시 주의**
           - labels와 values 배열 길이가 동일해야 함
           - values는 실제 숫자 (문자열 X)
           - **description은 반드시 자세하게 작성** (3문장 이상)
             예시: "40대 방문자가 38.5%로 가장 높은 비중을 차지합니다. 이는 문화예술 소비에 경제적 여유가 있는 연령대가 주요 타겟임을 보여줍니다. 30대와 50대도 각각 20% 이상으로 중장년층이 핵심 고객입니다."
        
        3. **데이터 해석 규칙**
           - review_stats의 rating_distribution → 평점 분포 bar 차트
           - demographics_stats의 age_distribution → 연령대 doughnut 차트
           - demographics_stats의 gender_distribution → 성별 doughnut 차트
           - 공연/전시 데이터 → 테이블
        
        4. **중요: 데이터에서 직접 값 추출**
           - 사전 계산된 통계(stats)가 있으면 그 값을 그대로 사용
           - 원본 데이터에서 필요한 값을 계산하여 사용
        
        # 시작
        위 데이터를 분석하고, 도구들을 호출하여 차트/테이블 블록을 생성하세요.
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
        
        # === 단계 1: 사전 계산된 통계에서 블록 + 인사이트 직접 생성 (LLM 스킵) ===
        calculated_stats, block_configs = _get_calculated_stats(research_payload)
        pre_generated_blocks = []
        pre_generated_insights = []
        
        if calculated_stats:
            pre_generated_blocks, pre_generated_insights = _create_blocks_from_calculated_stats(
                calculated_stats, block_configs
            )
            logger.info(f"[ANALYSE_AGENT] 사전 계산 통계에서 {len(pre_generated_blocks)}개 블록, {len(pre_generated_insights)}개 인사이트 생성")
            if block_configs:
                logger.info(f"[ANALYSE_AGENT] 블록 설정 사용: {list(block_configs.keys())}")
        
        # === 단계 2: 데이터 준비 (LLM용) ===
        data_text = _prepare_data_for_analysis(research_payload)
        
        # === 단계 3: 시스템 프롬프트 생성 ===
        # 사전 생성된 블록/인사이트 정보를 프롬프트에 포함
        pre_generated_info = ""
        if pre_generated_blocks:
            block_titles = [b.get("title", b.get("type", "")) for b in pre_generated_blocks]
            pre_generated_info = f"\n\n**주의: 다음 블록은 이미 생성되었으므로 다시 만들지 마세요:** {', '.join(block_titles)}"
        
        if pre_generated_insights:
            insights_text = "\n".join(pre_generated_insights)
            pre_generated_info += f"\n\n**이미 분석된 핵심 인사이트 (이를 바탕으로 추가 분석하세요):**\n{insights_text}"
        
        system_prompt = _build_analysis_prompt(
            report_type=report_type,
            org_name=org_name,
            report_topic=report_topic,
            data_text=data_text + pre_generated_info,
            latest_image=latest_image
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
        
        # === 단계 6.5: 분석 보고서 마크다운 생성 (LLM 기반) ===
        block_drafts = _add_analysis_report_markdown(
            block_drafts,
            report_type=report_type,
            org_name=org_name,
            report_topic=report_topic
        )
        logger.info(f"[ANALYSE_AGENT] 짝 마크다운 추가 후: {len(block_drafts)}개 블록")
        
        # === 단계 7: Fallback - 블록이 없으면 에러 메시지 ===
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
