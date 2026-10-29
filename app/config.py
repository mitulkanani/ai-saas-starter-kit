import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./saas.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-change-me-before-deployment")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if item.strip()
    )
    ai_provider: str = os.getenv("AI_PROVIDER", "mock").lower()
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_input_price_per_1m_usd: float = float(
        os.getenv("OPENAI_INPUT_PRICE_PER_1M_USD", "0.15")
    )
    openai_output_price_per_1m_usd: float = float(
        os.getenv("OPENAI_OUTPUT_PRICE_PER_1M_USD", "0.60")
    )
    default_monthly_token_limit: int = int(
        os.getenv("DEFAULT_MONTHLY_TOKEN_LIMIT", "10000")
    )


settings = Settings()
