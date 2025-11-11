from __future__ import annotations

import json
import textwrap
from typing import List


def create_final_report_compose_agent(llm):

    def compose_report_node(state):
        request_context = state.get("request_context", {})
        analysis_outline = state.get("analysis_outline", "")
        analysis_findings = state.get("analysis_findings", "")
        research_notes = state.get("research_notes", "")
        messages: List = list(state.get("messages", []))

        prompt = textwrap.dedent(
            """
            # 역할
            당신은 문화시설 전문 보고서 작성자입니다. 경영진이나 의사결정자를 위한 고품질 보고서를 작성합니다.
            
            # 목표
            조사 및 분석 단계에서 수집한 데이터와 인사이트를 바탕으로 실행 가능한 최종 보고서를 작성하세요.
            
            # 입력 자료
            요청 컨텍스트:
            {request_context}
            
            분석 개요:
            {analysis_outline}
            
            핵심 분석 결과:
            {analysis_findings}
            
            조사 메모:
            {research_notes}
            
            # 보고서 구조 (Markdown 형식)
            
            ## Executive Summary (핵심 요약)
            - 보고서의 목적과 주요 발견사항을 2-3 문단으로 요약
            - 의사결정자가 가장 먼저 읽는 섹션임을 고려
            - 핵심 메시지와 결론을 명확하게 제시
            
            ## Key Insights (주요 인사이트)
            - 데이터 분석을 통해 발견한 핵심 사실들을 번호나 불릿으로 정리
            - 각 인사이트는 구체적이고 데이터에 기반해야 함
            - 전시 정보, 소장품 정보 등 수집된 데이터를 적극 활용
            - 보고서 주제({report_topic})와 직접 연결
            
            ## Recommendations (제안사항)
            - 인사이트를 바탕으로 실행 가능한 제안을 제시
            - 각 제안은 구체적이고 측정 가능해야 함
            - 우선순위를 고려하여 정리
            - 문화시설의 특성과 현실을 반영
            
            ## Next Steps (향후 계획)
            - 제안사항을 실행하기 위한 구체적인 행동 계획
            - 단기/중기/장기 관점으로 구분 가능
            - 필요한 리소스나 협력 사항 명시
            - 실현 가능성을 고려한 로드맵
            
            # 작성 원칙
            1. 명확성: 전문 용어는 최소화하고 명확한 표현 사용
            2. 구체성: 모호한 표현 대신 구체적인 사실과 데이터 활용
            3. 실행 가능성: 실제로 실행할 수 있는 제안 제시
            4. 근거 기반: 모든 주장과 제안은 데이터와 분석에 근거
            5. 독자 중심: 의사결정자가 필요로 하는 정보에 집중
            
            # 형식 요구사항
            - Markdown 문법 사용 (제목, 불릿, 번호 목록 등)
            - 각 섹션은 명확하게 구분
            - 필요시 표나 리스트로 정보 정리
            - 한국어로 작성 (전문적이고 격식 있는 문체)
            - **중요**: 마크다운 코드 블록(```markdown 또는 ```)으로 감싸지 말고, 바로 마크다운 형식으로 작성하세요
            
            # 주의사항
            - 수집된 데이터를 최대한 활용하되, 없는 내용은 억지로 만들지 말 것
            - 일반론이나 상투적인 표현보다는 구체적인 내용에 집중
            - 보고서 주제와 질문들에 명확하게 답변할 것
            - 실제 전시 정보나 소장품 정보가 있다면 구체적으로 언급
            - **절대 코드 블록(```)으로 감싸지 말 것**: 보고서는 바로 마크다운 형식으로 시작해야 합니다
            
            위 구조와 원칙을 따라 완성도 높은 Markdown 보고서를 작성하세요. 
            보고서는 # 제목으로 바로 시작하고, 코드 블록 마커(```)를 사용하지 마세요.
            """
        ).format(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            report_topic=request_context.get("report_topic", "보고서 주제"),
            analysis_outline=analysis_outline,
            analysis_findings=analysis_findings,
            research_notes=research_notes,
        ).strip()

        response = llm.invoke(prompt)
        messages.append(response)
        final_report = response.content.strip() if response else "Report drafting is pending tool integration."

        return {
            "messages": messages,
            "final_report": final_report,
            "compose_prompt": prompt,
        }

    return compose_report_node
