from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Capstone Proto Backend"
    debug: bool = True
    
    # 기존 postgres DB (보고서 저장용 - deprecated, capstone으로 이전 예정)
    database_url: str
    
    # capstone DB (팀원 데이터 + 새 보고서 저장용)
    # 같은 RDS 서버, 다른 데이터베이스 이름
    capstone_database_url: str | None = None
    
    # LLM API 설정
    openai_api_key: str | None = None
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1500

    class Config:
        env_file = ".env"
        extra = "ignore"  # 정의되지 않은 환경 변수 무시


settings = Settings()