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
        latest_performance_image = state.get("latest_performance_image", "")
        messages: List = list(state.get("messages", []))
        
        # 보고서 타입에 따른 프롬프트 분기
        report_type = request_context.get("report_type", "user")
        
        # 사용자용/운영자용 보고서 프롬프트 분기
        if report_type == "operator":
            # 운영자용: 데이터 분석 중심 (제안보다는 분석에 집중)
            role_description = "당신은 문화시설 데이터 분석 전문가입니다. 주어진 데이터를 충분히 활용하여 이 기관에 대한 심층 분석 보고서를 작성합니다."
            target_audience = "운영진과 경영진"
            report_focus = """
            - **데이터 기반 분석이 핵심**: 주어진 모든 데이터(연령대별 성별 비율, 구글맵 리뷰 평점 분포, 전시/공연 정보 등)를 충분히 활용한 분석
            - **인기 타겟 분석**: 누구에게 인기가 제일 많은지 (연령대별, 성별 방문자 통계 분석)
            - **리뷰 분석**: 구글맵 리뷰를 종합하여 각 별점(5점, 4점, 3점, 2점, 1점)을 주는 이유와 패턴 분석
            - **트렌드 분석**: 수집된 데이터를 바탕으로 한 시설의 특성과 트렌드 분석
            - **중요**: 이상한 인사이트나 추측이 아닌, 주어진 데이터를 기반으로 한 객관적이고 구체적인 분석에 집중
            """
            writing_style = "전문적이고 데이터 중심이며, 분석의 깊이와 정확성을 보여주는 것이 핵심. 보고서를 읽었을 때 '이 기관에 대한 분석이 잘 되었다'는 느낌을 주어야 함"
        else:
            # 사용자용: 시설 소개 및 즐기는 방법 제안
            role_description = "당신은 문화시설 안내 전문가입니다. 주어진 데이터를 활용하여 일반 이용자에게 이 시설이 어떤 곳인지, 어떻게 즐기는 게 좋은지, 왜 와야 하는지를 납득시킬 수 있는 보고서를 작성합니다."
            target_audience = "일반 이용자"
            report_focus = """
            - **시설 소개**: 주어진 데이터를 활용하여 이 시설이 어떤 장소인지 설명
            - **즐기는 방법**: 이 장소를 잘 즐길 수 있는 방법 제안 (전시/공연 정보, 프로그램, 체험 활동 등)
            - **방문 이유**: 이곳을 와야 하는 이유를 설득력 있게 제시
            - **실용 정보**: 실제 방문 시 유용한 정보 (위치, 교통, 운영 시간, 관람료, 예약 방법 등)
            - **중요**: 사용자가 이 장소에 대해 이해하고 방문하고 싶게 만드는 것이 목표
            """
            writing_style = "친절하고 이해하기 쉬우며, 설득력 있고 매력적인 문체. 실제 방문 시 유용한 실용적 정보 중심"

        # 이미지 섹션 구성 (프롬프트 템플릿 정의 전에 먼저 정의)
        if latest_performance_image:
            # 기관명에 따라 이미지 설명 변경
            org_name = request_context.get("organization_name", "")
            if "예술의전당" in org_name or "예술의 전당" in org_name:
                image_label = "가장 최근 공연"
            elif "국립현대미술관" in org_name or "미술관" in org_name:
                image_label = "가장 최근 전시"
            else:
                image_label = "가장 최근 이미지"
            
            image_section = f"""
            # {image_label} 이미지
            가장 최근 {image_label} 이미지 URL: {latest_performance_image}
            """
            image_instruction = f"""
            - **{image_label} 이미지 포함**: 위에 제공된 가장 최근 {image_label} 이미지 URL을 보고서에 포함하세요.
            - 이미지는 {"분석 요약" if report_type == "operator" else "이 시설은 어떤 곳인가요?"} 섹션 바로 아래에 HTML 형식으로 추가하세요: <img src="이미지URL" alt="{image_label}" style="max-width: 100%; height: auto;" />
            - 이미지가 보고서 가로폭을 넘지 않도록 max-width: 100% 스타일을 반드시 적용하세요.
            - 이미지가 보고서의 시각적 효과를 높이므로 반드시 포함하세요.
            """
        else:
            image_section = ""
            image_instruction = ""

        # request_context를 JSON 문자열로 변환 (중괄호 이스케이프)
        request_context_str = json.dumps(request_context, ensure_ascii=False, indent=2).replace('{', '{{').replace('}', '}}')
        
        prompt = textwrap.dedent(
            f"""
            # 역할
            {role_description}
            
            # 목표
            조사 및 분석 단계에서 수집한 데이터와 인사이트를 바탕으로 {target_audience}를 위한 최종 보고서를 작성하세요.
            
            # 보고서 초점
            {report_focus}
            
            # 입력 자료
            요청 컨텍스트:
            {request_context_str}
            
            분석 개요:
            {analysis_outline}
            
            핵심 분석 결과:
            {analysis_findings}
            
            조사 메모:
            {research_notes}
            
            {image_section}
            
            # 보고서 구조 (Markdown 형식)
            
            {"## 분석 요약" if report_type == "operator" else "## 이 시설은 어떤 곳인가요?"}
            {"- 수집된 데이터를 종합한 핵심 분석 결과를 2-3 문단으로 요약" if report_type == "operator" else "- 주어진 데이터를 활용하여 이 시설이 어떤 장소인지 설명"}
            {"- 분석의 주요 발견사항과 데이터 기반 인사이트를 명확하게 제시" if report_type == "operator" else "- 이 시설의 특징, 역사, 주요 콘텐츠 등을 소개하여 이용자가 이곳을 이해할 수 있도록"}
            
            {"## 방문객 분석" if report_type == "operator" else "## 어떻게 즐기면 좋을까요?"}
            {"- 연령대별, 성별 방문자 통계를 분석하여 누구에게 인기가 제일 많은지 분석" if report_type == "operator" else "- 이 장소를 잘 즐길 수 있는 방법 제안"}
            {"- 방문객 패턴과 트렌드를 데이터 기반으로 분석" if report_type == "operator" else "- 추천 프로그램, 체험 활동, 관람 팁 등 실제 방문 시 유용한 정보"}
            {"- 수집된 연령대별 성별 비율 데이터를 구체적으로 활용하여 분석" if report_type == "operator" else "- 전시/공연 정보, 특별 이벤트, 교육 프로그램 등을 소개"}
            
            {"## 리뷰 분석" if report_type == "operator" else "## 왜 이곳을 방문해야 할까요?"}
            {"- 구글맵 리뷰 평점 분포 데이터를 종합하여 각 별점(5점, 4점, 3점, 2점, 1점)을 주는 이유와 패턴 분석" if report_type == "operator" else "- 이곳을 와야 하는 이유를 설득력 있게 제시"}
            {"- 평점별 리뷰 특징과 고객 만족도 요인 분석" if report_type == "operator" else "- 이 시설만의 특별함, 방문 가치, 추천 포인트 등을 제시"}
            {"- 평균 평점과 총 리뷰 수를 포함한 구체적인 데이터 분석" if report_type == "operator" else "- 이용자 후기나 평가를 참고하여 방문 동기를 부여"}
            
            {"## 종합 분석" if report_type == "operator" else "## 이용 안내"}
            {"- 모든 수집 데이터(연령대별 성별 비율, 리뷰 통계, 전시/공연 정보 등)를 종합하여 이 기관의 특성과 트렌드 분석" if report_type == "operator" else "- 방문 시 알아두면 좋은 실용적 정보"}
            {"- 데이터 간 연관성 분석 및 종합 인사이트 도출" if report_type == "operator" else "- 위치, 교통편, 운영 시간, 관람료, 예약 방법 등"}
            {"- **중요**: 제안보다는 분석에 집중. 보고서를 읽었을 때 '분석이 잘 되었다'는 느낌을 주어야 함" if report_type == "operator" else "- 이용 팁과 주의사항"}
            
            # 작성 원칙
            {"1. 데이터 중심: 주어진 모든 데이터를 충분히 활용하여 분석. 추측이나 일반론이 아닌 구체적인 데이터 기반 분석" if report_type == "operator" else "1. 설득력: 이 시설이 어떤 곳인지, 어떻게 즐기는 게 좋은지, 왜 와야 하는지를 납득시킬 수 있도록"}
            {"2. 분석의 깊이: 단순 나열이 아닌 데이터 간 연관성과 패턴을 분석하여 '분석이 잘 되었다'는 느낌을 줌" if report_type == "operator" else "2. 구체성: 모호한 표현 대신 구체적인 사실과 데이터 활용"}
            {"3. 객관성: 이상한 인사이트나 추측이 아닌, 주어진 데이터를 기반으로 한 객관적이고 구체적인 분석" if report_type == "operator" else "3. 실용성: 실제 방문 시 바로 활용할 수 있는 정보 제공"}
            {"4. 제안 최소화: 제안보다는 분석에 집중. 분석 자체가 핵심임" if report_type == "operator" else "4. 근거 기반: 모든 정보는 수집된 데이터에 근거"}
            {"5. 종합성: 연령대별 성별 비율, 리뷰 통계, 전시/공연 정보 등을 종합하여 분석" if report_type == "operator" else "5. 독자 중심: 이용자가 필요로 하는 정보에 집중"}
            
            # 형식 요구사항
            - Markdown 문법 사용 (제목, 불릿, 번호 목록 등)
            - 각 섹션은 명확하게 구분
            - 필요시 표나 리스트로 정보 정리
            - 한국어로 작성 ({writing_style})
            - **중요**: 마크다운 코드 블록(```markdown 또는 ```)으로 감싸지 말고, 바로 마크다운 형식으로 작성하세요
            {image_instruction}
            
            # 주의사항
            - 수집된 데이터를 최대한 활용하되, 없는 내용은 억지로 만들지 말 것
            - 일반론이나 상투적인 표현보다는 구체적인 내용에 집중
            - 보고서 주제와 질문들에 명확하게 답변할 것
            - 실제 수집된 정보(전시, 공연, 프로그램 등)가 있다면 구체적으로 언급하되, 기관의 특성에 맞게 자연스럽게 작성
            - 각 기관의 특성에 맞게 보고서를 작성하세요 (예: 예술의전당은 공연 중심, 박물관은 전시 중심 등)
            - **절대 코드 블록(```)으로 감싸지 말 것**: 보고서는 바로 마크다운 형식으로 시작해야 합니다
            
            위 구조와 원칙을 따라 완성도 높은 Markdown 보고서를 작성하세요. 
            보고서는 # 제목으로 바로 시작하고, 코드 블록 마커(```)를 사용하지 마세요.
            """
        )
        
        # f-string에서 이미 모든 변수가 치환되었으므로 추가 format 불필요
        prompt = prompt.strip()

        response = llm.invoke(prompt)
        messages.append(response)
        final_report = response.content.strip() if response else "Report drafting is pending tool integration."

        return {
            "messages": messages,
            "final_report": final_report,
            "compose_prompt": prompt,
        }

    return compose_report_node
