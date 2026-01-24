import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Matching settings
    enable_ml_matching: bool = (
        os.getenv("ENABLE_ML_MATCHING", "false").lower() == "true"
    )

    # Google Gemini Embeddings (Free, 0 RAM)
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")

    # LLM Matching (OpenRouter is OPTIONAL now, primary is Google Relay)
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")

    # OCR для рукописных заказов (Vision LLM)
    ocr_model: str = os.getenv("OCR_MODEL", "qwen/qwen3-vl-32b-instruct")
    fuzzy_threshold: int = (
        70  # Понижен с 75 для better recall (муфты 202 имеют score 73)
    )
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
