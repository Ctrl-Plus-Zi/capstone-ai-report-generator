import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    api_key: Optional[str] = None


class SimpleReportService:
    def __init__(self, config: LLMConfig = None):
        if config is None:
            config = LLMConfig(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                api_key=settings.openai_api_key
            )
        self.config = config
    
    def generate_prompt(self, organization_name: str, question: str) -> str:
        today = datetime.now().strftime("%Y년 %m월 %d일")
        
        prompt = f"""당신은 전문 비즈니스 분석가입니다. 다음 질문에 대해 전문적이고 상세하게 답변해주세요.


**기관명:** {organization_name}
**질문:** {question}
**분석 기준일:** {today}

다음 지침을 따라 답변해주세요:
1. 객관적이고 전문적인 분석을 제공하세요
2. 구체적인 근거와 데이터를 바탕으로 설명하세요
3. 한국어로 명확하게 작성하세요
4. 실행 가능한 인사이트를 포함하세요

답변:"""
        
        return prompt
    
    def _generate_dummy_response(self, prompt: str) -> str:
        """테스트용 더미 응답 생성"""
        return """이것은 테스트용 더미 응답입니다.
        
실제 API가 연결되면 여기에 전문적인 분석 내용이 제공될 것입니다.
현재는 OpenAI API 키가 설정되지 않았거나 API 호출에 실패했습니다."""

    async def generate_report(self, organization_name: str, question: str) -> str:
        """보고서 생성 메서드"""
        # 프롬프트 생성
        prompt = self.generate_prompt(organization_name, question)
        
        # LLM API 호출하여 응답 받기
        response = await self.call_llm_api(prompt)
        
        return response

    async def call_llm_api(self, prompt: str) -> str:
        try:
            # API 키 확인
            api_key = self.config.api_key or settings.openai_api_key
            if not api_key or api_key == "your_openai_api_key_here":
                logger.warning("OpenAI API 키가 설정되지 않음. ")
                return self._generate_dummy_response(prompt)
            
            # OpenAI API 호출
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {
                            "role": "system", 
                            "content": "당신은 전문적인 비즈니스 분석가입니다. 정확하고 유용한 정보를 제공하세요."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                
                return response.choices[0].message.content
                
            except ImportError:
                logger.error("openai 라이브러리가 설치되지 않음")
                return self._generate_dummy_response(prompt)
                
        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            return self._generate_dummy_response(prompt)


# 싱글톤 인스턴스
simple_report_service = SimpleReportService()