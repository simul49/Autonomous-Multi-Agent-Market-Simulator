"""Application configuration with multi-provider AI settings."""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── Database ──
    DB_ENGINE: str = "mysql"
    DB_NAME: str = "MarketSimulator"
    DB_USER: str = "root"
    DB_PASSWORD: str = "paradox49"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306

    @property
    def database_url(self) -> str:
        engine = os.environ.get("DB_ENGINE", self.DB_ENGINE)
        if engine == "sqlite":
            return "sqlite:///./amms.db"
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            "?charset=utf8mb4"
        )

    # ── AI Providers (ordered fallback: DeepSeek → Qwen → Hunyuan) ──
    DEEPSEEK_API_KEY: str = "sk-10005a835c3b46a3922f30de3bc932cd"
    DEEPSEEK_ALT_API_KEY: str = "sk-abc7c7dd4f664ea885af1ec4c53dfc6d"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    QWEN_API_KEY: str = "sk-a55dee8a343f4ddc87a283bfe1070289"
    HUNYUAN_API_KEY: str = "sk-7z1l0uyFz1APEM3j0KXgHOqPNO8vHQWqUBP3weYuEC03sAqR"

    # ── Simulation Defaults ──
    DEFAULT_AGENT_COUNT: int = 50
    DEFAULT_PRODUCT_COUNT: int = 20
    DEFAULT_MERCHANT_COUNT: int = 5
    INCOME_PER_TICK: float = 15.0
    INCOME_INTERVAL_TICKS: int = 10
    MAX_CONCURRENT_WORKERS: int = 100

    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
