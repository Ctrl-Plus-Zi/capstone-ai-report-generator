from __future__ import annotations

import json
import textwrap
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
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
        research_payload = state.get("research_payload", [])
        messages: List = list(state.get("messages", []))
        
        # 보고서 타입에 따른 프롬프트 분기
        report_type = request_context.get("report_type", "user")
        
        # 사용자용/운영자용 분석 프롬프트 분기
        if report_type == "operator":
            # 운영자용: 데이터 분석 중심 (제안보다는 분석에 집중)
            role_description = "당신은 문화시설 데이터 분석 전문가입니다. 주어진 데이터를 충분히 활용하여 이 기관에 대한 심층 분석을 수행합니다."
            goal_description = "조사 에이전트가 수집한 모든 데이터를 분석하여, 이 기관에 대한 객관적이고 구체적인 분석 결과를 정리하세요. 이상한 인사이트나 추측이 아닌, 데이터 기반 분석이 핵심입니다."
            focus_description = """
            - **데이터 기반 분석**: 연령대별 성별 비율, 구글맵 리뷰 평점 분포, 전시/공연 정보 등 모든 수집 데이터를 충분히 활용
            - **인기 타겟 분석**: 누구에게 인기가 제일 많은지 (연령대별, 성별 방문자 통계 분석)
            - **리뷰 분석**: 구글맵 리뷰를 종합하여 각 별점(5점, 4점, 3점, 2점, 1점)을 주는 이유와 패턴 분석
            - **트렌드 분석**: 수집된 데이터를 바탕으로 한 시설의 특성과 트렌드 분석
            - **중요**: 제안보다는 분석에 집중. 분석 자체가 핵심이며, 보고서를 읽었을 때 '분석이 잘 되었다'는 느낌을 주어야 함
            """
        else:
            # 사용자용: 시설 소개 및 즐기는 방법 제안
            role_description = "당신은 문화시설 안내 전문가입니다. 수집된 데이터를 분석하여 일반 이용자에게 이 시설이 어떤 곳인지, 어떻게 즐기는 게 좋은지, 왜 와야 하는지를 납득시킬 수 있는 정보를 제공합니다."
            goal_description = "조사 에이전트가 수집한 데이터를 분석하고, 이용자에게 이 시설에 대한 이해와 방문 동기를 부여할 수 있는 정보를 정리하세요."
            focus_description = """
            - **시설 소개**: 이 시설이 어떤 장소인지 설명할 수 있는 정보
            - **즐기는 방법**: 이 장소를 잘 즐길 수 있는 방법 (전시/공연 정보, 프로그램, 체험 활동 등)
            - **방문 이유**: 이곳을 와야 하는 이유를 제시할 수 있는 정보
            - **실용 정보**: 실제 방문 시 유용한 정보 (위치, 교통, 운영 시간, 관람료 등)
            """

        # request_context를 JSON 문자열로 변환 (중괄호 이스케이프하여 ChatPromptTemplate이 변수로 인식하지 않도록)
        request_context_str = json.dumps(request_context, ensure_ascii=False, indent=2).replace('{', '{{').replace('}', '}}')
        research_sources_str = json.dumps(research_sources, ensure_ascii=False, indent=2).replace('{', '{{').replace('}', '}}')
        research_notes_str = str(research_notes).replace('{', '{{').replace('}', '}}')
        research_payload_str = json.dumps(research_payload, ensure_ascii=False, indent=2).replace('{', '{{').replace('}', '}}')
        
        system_text = textwrap.dedent(
            f"""
            # 역할
            {role_description}
            
            # 목표
            {goal_description}
            
            # 분석 초점
            {focus_description}
            
            # 입력 데이터
            요청 컨텍스트: {request_context_str}
            조사 메모: {research_notes_str}
            참고 출처: {research_sources_str}
            수집된 데이터 샘플: {research_payload_str}
            
            # 분석 프레임워크
            1. 데이터 검토
               - 수집된 데이터의 양과 품질 평가
               - 수집된 모든 데이터 유형 파악 (기관에 따라 전시, 공연, 프로그램 등이 다를 수 있음)
               - 데이터 간 연관성 분석
            
            2. 패턴 및 트렌드 파악
               - 수집된 데이터에서 발견되는 패턴과 트렌드 분석
               - 기관의 특성과 강점 파악
               - 방문객과 이용자 행동 패턴 분석
            
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
            - 보고서 타입({report_type})에 맞는 독자에게 유용한 정보에 집중하세요
            - {"운영진을 위한 데이터 분석과 전략적 제안에 집중하세요." if report_type == "operator" else "일반 이용자를 위한 실용적이고 접근하기 쉬운 정보에 집중하세요."}
            """
        ).strip()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_text),
                MessagesPlaceholder(variable_name="messages"),
            ]
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
