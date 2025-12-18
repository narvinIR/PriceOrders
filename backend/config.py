import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Matching settings
    fuzzy_threshold: int = 85
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
