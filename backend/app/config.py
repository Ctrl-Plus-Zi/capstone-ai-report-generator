from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Capstone Proto Backend"
    debug: bool = True
    database_url: str
    
    # LLM API 설정
    openai_api_key: str | None = None
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1500

    class Config:
        env_file = ".env"


settings = Settings()
