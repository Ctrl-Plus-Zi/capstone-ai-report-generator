from __future__ import annotations
import json
import textwrap
from typing import List

from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 수집된 자료를 분석하고 보고서 초안을 작성하는 분석 에이전트 노드 생성 
def create_analyse_agent(tool_llm, summary_llm, toolkit):

    def analyse_agent_node(state):
        tools = [
            toolkit.analyse_quantitative_metrics,
            toolkit.analyse_qualitative_feedback,
        ]

        request_context = state.get("request_context", {})
        research_notes = state.get("research_notes", "")
        research_sources = state.get("research_sources", [])
        messages: List = list(state.get("messages", []))

        system_text = textwrap.dedent(
            """
            # 역할
            당신은 문화시설 데이터 분석 전문가입니다. 수집된 데이터를 심층 분석하여 의미 있는 인사이트를 도출합니다.
            
            # 목표
            조사 에이전트가 수집한 데이터를 분석하고, 보고서 작성에 필요한 핵심 발견사항을 정리하세요.
            
            # 입력 데이터
            요청 컨텍스트: {request_context}
            조사 메모: {research_notes}
            참고 출처: {research_sources}
            
            # 분석 프레임워크
            1. 데이터 검토
               - 수집된 데이터의 양과 품질 평가
               - 전시 정보, 소장품 정보 등 데이터 유형 파악
               - 데이터 간 연관성 분석
            
            2. 패턴 및 트렌드 파악
               - 전시 기간, 주제, 관람료 등의 패턴
               - 소장품의 시대별, 유형별 분포
               - 기관의 특성과 강점 파악
            
            3. 보고서 주제와의 연결
               - 수집된 데이터가 report_topic과 어떻게 관련되는지 분석
               - questions 리스트의 각 질문에 대한 답변 도출
               - 부족한 정보나 추가 필요한 분석 식별
            
            4. 핵심 인사이트 도출
               - 데이터에서 발견한 주요 사실
               - 의미 있는 통찰과 해석
               - 보고서 작성에 활용할 수 있는 결론
            
            # 분석 도구 (현재 구현 예정)
            - analyse_quantitative_metrics: 정량적 지표 분석
            - analyse_qualitative_feedback: 정성적 피드백 분석
            
            # 출력 요구사항
            다음 내용을 포함한 분석 결과를 작성하세요:
            1. 데이터 요약: 수집된 데이터의 주요 특징
            2. 발견사항: 데이터 분석을 통해 발견한 중요한 사실들
            3. 인사이트: 데이터가 보고서 주제에 주는 시사점
            4. 제언: 보고서 작성 시 강조할 포인트
            
            # 주의사항
            - 수집된 데이터가 부족하더라도 가능한 한 의미 있는 분석을 제공하세요
            - 추측이 아닌 데이터 기반의 분석을 수행하세요
            - 보고서 독자(의사결정자)에게 유용한 정보에 집중하세요
            """
        ).strip()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_text),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            research_notes=research_notes,
            research_sources=json.dumps(research_sources, ensure_ascii=False, indent=2),
        )


        chain = prompt | tool_llm.bind_tools(tools)
        ai_response = chain.invoke({"messages": messages})
        messages.append(ai_response)

        analysis_outline = getattr(ai_response, "content", "").strip()
        analysis_findings = state.get("analysis_findings")

        if hasattr(ai_response, "tool_calls"):
            for call in ai_response.tool_calls:
                tool_fn = next((t for t in tools if t.name == call.get("name")), None)
                if tool_fn is None:
                    continue
                tool_args = call.get("args", {})
                tool_result = tool_fn.invoke(tool_args)
                messages.append(
                    ToolMessage(
                        tool_call_id=call.get("id"),
                        content=json.dumps(tool_result) if tool_result is not None else "{}",
                    )
                )
                if isinstance(tool_result, dict):
                    notes = tool_result.get("analysis_notes")
                    if notes:
                        note_entry = f"- {notes}"
                        analysis_outline = (
                            f"{analysis_outline}\n{note_entry}".strip() if analysis_outline else note_entry
                        )

        summary_input = analysis_outline or research_notes
        summary_messages = [
            SystemMessage(content=textwrap.dedent("""
                수집된 데이터와 분석 내용을 바탕으로 핵심 발견사항을 요약하세요.
                
                요약 시 포함할 내용:
                1. 주요 데이터 포인트 (전시 개수, 소장품 특성 등)
                2. 발견한 패턴이나 트렌드
                3. 보고서 주제와의 연결점
                4. 핵심 인사이트와 시사점
                
                간결하고 명확하게 작성하되, 중요한 정보는 누락하지 마세요.
            """).strip()),
            HumanMessage(content=summary_input or "분석 입력이 제공되지 않았습니다."),
        ]
        summary_response = summary_llm.invoke(summary_messages)
        messages.append(summary_response)
        analysis_findings = summary_response.content.strip() if summary_response else (analysis_findings or "")

        if not analysis_outline:
            analysis_outline = "도구와 LLM 분석이 완료되면 이 부분을 채워 주세요."
        if not analysis_findings:
            analysis_findings = "도구 통합이 완료되면 분석 결과가 생성됩니다."

        return {
            "messages": messages,
            "analysis_outline": analysis_outline,
            "analysis_findings": analysis_findings,
        }

    return analyse_agent_node
