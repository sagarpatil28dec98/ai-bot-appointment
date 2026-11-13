from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "HealthAI-Assistant"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "super_secret_64_char_key_change_in_production_1234567890"
    WEBHOOK_SECRET: str = "healthai_webhook_secret_for_n8n_and_openwa"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://healthai:healthai_secure_pass@postgres:5432/healthai_db"
    SYNC_DATABASE_URL: str = "postgresql://healthai:healthai_secure_pass@postgres:5432/healthai_db"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # n8n Orchestration URL
    N8N_BASE_URL: str = "https://n8n.geetrix.com"
    N8N_CONFIRMATION_WEBHOOK_URL: str = "https://n8n.geetrix.com/webhook/booking-confirmed"

    # WhatsApp / OpenWA
    OPENWA_URL: str = "http://openwa:8080"
    OPENWA_API_KEY: str = "openwa_secure_api_key_123"

    # LLM Settings
    LLM_PROVIDER: str = "ollama"  # or openai, mock
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "llama3.2:latest"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Calendar Integration
    GOOGLE_CALENDAR_CREDENTIALS_PATH: str = "/app/credentials/google_service_account.json"
    GOOGLE_CALENDAR_DEFAULT_ID: str = "primary"
    GOOGLE_CALENDAR_TIMEZONE: str = "Asia/Kolkata"
    USE_MOCK_GOOGLE_CALENDAR: bool = True

    # Seed Admin User
    DEFAULT_ADMIN_EMAIL: str = "admin@clinic.com"
    DEFAULT_ADMIN_PASSWORD: str = "AdminSecurePass123!"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
