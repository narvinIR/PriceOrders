import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Matching settings
    enable_ml_matching: bool = os.getenv("ENABLE_ML_MATCHING", "false").lower() == "true"

    # LLM Matching (OpenRouter) - замена тяжёлого embedding
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "moonshotai/kimi-k2-thinking")
    fuzzy_threshold: int = 70  # Понижен с 75 для better recall (муфты 202 имеют score 73)
    confidence_exact_sku: float = 100.0
    confidence_exact_name: float = 95.0
    confidence_fuzzy_sku: float = 90.0
    confidence_fuzzy_name: float = 80.0
    confidence_ml: float = 70.0
    min_confidence_auto: float = 80.0

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
