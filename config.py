from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

BASE_DIR    = Path(__file__).parent
OUTPUT_DIR  = BASE_DIR / "output"
RESULTS_DIR = BASE_DIR / "results"
SAMPLES_DIR = BASE_DIR / "samples"

for _d in (OUTPUT_DIR, RESULTS_DIR, SAMPLES_DIR):
    _d.mkdir(exist_ok=True)


class Settings(BaseSettings):
    # Gemini — image fuzzer + 텍스트 뮤테이션 provider
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model:   str = Field(default="gemini-2.0-flash", env="GEMINI_MODEL")

    # 기타 LLM providers — 텍스트 뮤테이션 provider 선택 시 사용
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    openai_api_key:    str = Field(default="", env="OPENAI_API_KEY")

    # 쇼핑몰 챗봇 API (옵션 — 없으면 Gemini 직접 호출)
    chatbot_endpoint: str = Field(default="", env="CHATBOT_ENDPOINT")
    chatbot_api_key:  str = Field(default="", env="CHATBOT_API_KEY")

    # Image fuzzer 실행 설정
    request_delay_sec:   float = Field(default=4.0,  env="REQUEST_DELAY_SEC")
    max_retries:         int   = Field(default=3,    env="MAX_RETRIES")
    save_mutated_images: bool  = Field(default=True, env="SAVE_MUTATED_IMAGES")

    class Config:
        env_file = str(BASE_DIR / ".env")
        extra    = "ignore"


settings = Settings()
