from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Facebook / Meta
    fb_app_id: str = ""
    fb_app_secret: str = ""
    fb_verify_token: str = "my_verify_token_123"
    fb_page_access_token: str = ""  # Deprecated: Use OAuth instead

    # AI
    anthropic_api_key: str = ""
    kilo_api_key: str = ""  # Fallback: Kilo Gateway free models

    # Database (SQLite for local/testing, PostgreSQL for production)
    database_url: str = "sqlite:///./ecom_agent.db"

    # App
    app_url: str = "http://localhost:8000"
    port: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
