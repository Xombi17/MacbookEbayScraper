"""
Centralized configuration for the MacBook Deal Intelligence System.
All settings are loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Scraping ──────────────────────────────────────────────────
    firecrawl_api_key: str = Field(..., description="Firecrawl API key")

    # ── AI (GitHub Models) ────────────────────────────────────────
    gh_models_token: str = Field(..., description="GitHub personal access token for GitHub Models")
    gh_chat_model: str = Field("gpt-4o", description="GitHub Models model name")
    gh_models_endpoint: str = Field(
        "https://models.inference.ai.azure.com",
        description="GitHub Models inference endpoint",
    )

    # ── Telegram ──────────────────────────────────────────────────
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    telegram_chat_id: str = Field(..., description="Telegram chat ID")

    # ── Database ──────────────────────────────────────────────────
    mongodb_uri: str | None = Field(None, description="MongoDB Atlas connection URI")

    # ── Pipeline Settings ─────────────────────────────────────────
    deal_score_threshold: float = Field(7.0, ge=0.0, le=10.0)
    max_price_usd: float = Field(1500.0, gt=0)
    run_interval_hours: int = Field(6, ge=1, le=24)
    daily_credit_limit: int = Field(50, ge=1)

    # ── Feature Flags ─────────────────────────────────────────────
    enable_ai_filter: bool = Field(True)
    enable_telegram: bool = Field(True)
    admin_api_key: str = Field("change-me-in-production", description="API key to protect scraping trigger endpoint")

    # ── App Meta ──────────────────────────────────────────────────
    app_name: str = "MacBook Deal Intelligence"
    app_version: str = "1.0.0"
    debug: bool = Field(False)

    def get_database_url(self) -> str:
        """Returns the appropriate async database URL."""
        if self.database_type == "postgresql":
            if not self.database_url:
                raise ValueError("DATABASE_URL must be set when DATABASE_TYPE=postgresql")
            return self.database_url
        # SQLite async URL
        return f"sqlite+aiosqlite:///{self.sqlite_path}"


# ── Static constants ──────────────────────────────────────────────────────────

SEARCH_QUERIES: list[str] = [
    # Top Priority: Newest Max models with high RAM, excluding common junk
    "MacBook Pro (M1, M2, M3, M4, M5) Max (\"64GB\", \"32GB\", \"96GB\", \"128GB\") -(broken, parts, locked, icloud, cracked, mdm, as is)"
]

BAD_KEYWORDS: list[str] = [
    "icloud lock",
    "activation lock",
    "mdm",
    "jamf",
    "dep enrolled",
    "for parts",
    "broken",
    "cracked",
    "water damage",
    "read description",
    "no power",
    "parts only",
    "missing",
    "untested",
    "as is",
]

# Singleton accessor
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
