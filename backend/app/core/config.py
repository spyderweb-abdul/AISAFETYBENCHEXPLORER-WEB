from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/aisafetybenchexplorer"
    SECRET_KEY: str = "change-me-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_MODEL: str = "openai/gpt-4o"

    # Ollama integration: routes ollama/* model_used values (DeepSeek,
    # Qwen, Kimi, and other open-weight models) through Ollama's
    # OpenAI-compatible /v1/chat/completions endpoint via the same
    # openai SDK already used for OpenAI itself -- see
    # app/core/agent_runner.py's _call_ollama().
    #
    # OLLAMA_BASE_URL_CLOUD defaults to Ollama Cloud's hosted endpoint
    # (https://ollama.com/v1), verified 2026-08-16. This is the setting
    # used in production per the team's stated preference for Ollama
    # Cloud over self-hosting. Override in .env only if pointing at a
    # different Ollama-compatible host.
    #
    # OLLAMA_BASE_URL_LOCAL is for a self-hosted Ollama instance
    # (typically http://localhost:11434/v1 or a container hostname) --
    # not used by the current dispatch logic, which only reads
    # OLLAMA_BASE_URL_CLOUD, but kept available for a future local/dev
    # override if needed.
    #
    # OLLAMA_API_KEY is REQUIRED for Ollama Cloud (create one at
    # https://ollama.com/settings/keys) -- local Ollama does not need
    # one. Leaving this unset will cause any ollama/* job to fail with
    # a clear error from _call_ollama() rather than a confusing auth
    # failure from the SDK.
    OLLAMA_BASE_URL_CLOUD: str = "https://ollama.com/v1"
    OLLAMA_BASE_URL_LOCAL: str = ""
    OLLAMA_NATIVE_URL: str = ""
    OLLAMA_API_KEY: str = ""

    SEMANTIC_SCHOLAR_API_KEY: str = ""

    GITHUB_TOKEN: str = ""
    HF_TOKEN: str = ""
    REDIS_URL: str = "redis://redis:6379/0"

    POPULAR_CITATION_THRESHOLD: int = 500

    # Phase 6 item 4: community submission workflow.
    COMMUNITY_SUBMISSION_MODEL: str = "ollama/gpt-oss:120b-cloud"
    MIN_QUALITY_SCORE_FOR_REVIEW: float = 0.5
    MAX_CONSECUTIVE_REJECTIONS: int = 3

    # Phase 6 item 3: notifications. Email is best-effort and optional
    # -- an in-app Notification row is ALWAYS written regardless of
    # whether SMTP is configured. Leave SMTP_HOST blank to disable
    # email entirely (development default).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@aisafetybenchexplorer.local"
    SMTP_USE_TLS: bool = True
    # Comma-separated list is not used here on purpose -- admin
    # recipients are looked up dynamically as every User with
    # role="admin" at notification time (see notify_admins()), so
    # adding/removing an admin account automatically changes who gets
    # notified without an .env edit. Kept here only as an optional
    # override/addition for admin addresses that don't have a user
    # account in this system at all (e.g. a shared ops inbox).
    ADMIN_NOTIFICATION_EMAILS_EXTRA: str = ""
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()