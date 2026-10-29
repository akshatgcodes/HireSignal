from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./hiresignal.db"
    # Celery broker and the per-host rate limiter. Empty → no limiter (fine for tests)
    redis_url: str = ""
    celery_always_eager: bool = False  # run tasks inline, no worker (tests, quick local runs)
    app_password: str = ""
    session_secret: str = "dev-insecure-secret"
    frontend_url: str = "http://localhost:5173"
    cross_site_cookies: bool = False

    # Nightly scan, then the morning digest (both in this timezone)
    timezone: str = "Asia/Kolkata"
    scan_hour: int = 2
    digest_hour: int = 8
    digest_to: str = ""  # empty → digest is built and saved, but not emailed
    # Hosts without a Celery worker: an outside scheduler POSTs /api/cron/* with this secret
    cron_secret: str = ""

    # Outgoing HTTP. Identify ourselves and stay well under any rate limit
    user_agent: str = "HireSignal/0.1 (personal job tracker)"
    http_timeout: float = 20.0
    host_interval: float = 2.0  # seconds between two requests to the same host
    news_days: int = 30
    news_per_company: int = 15

    # LLM via any OpenAI-compatible endpoint (Groq by default). No key → keyword fallback
    llm_api_key: str = ""
    groq_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"
    llm_max_tokens: int = 4000

    # SMTP (Mailpit in docker-compose: host=mailpit, port=1025, no auth)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    mail_from: str = "HireSignal <digest@hiresignal.local>"
    public_url: str = "http://localhost:5173"  # used for links in the email

    @property
    def llm_key(self) -> str:
        return self.llm_api_key or self.groq_api_key


settings = Settings()
