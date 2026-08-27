# Destination path: backend/app/core/config.py
# Replaces the existing file in full.
#
# CHANGES (Phase 6 items 3/4, this session):
# - COMMUNITY_SUBMISSION_MODEL: the forced model_used value for every
#   community submission's initial extraction attempt. Defaults to
#   ollama/gpt-oss:120b-cloud -- confirmed via web search (2026-08)
#   to be a free-tier-accessible, highly capable Ollama Cloud model,
#   distinct from the six models confirmed gated behind a paid
#   subscription (Known Gap item 17: deepseek-v4-pro, deepseek-v4-
#   flash, kimi-k3, kimi-k2.6, qwen3.5:397b, qwen3-coder:480b). This
#   keeps community submissions from consuming any paid OpenAI/
#   Anthropic token budget or hitting Ollama's paid-tier wall.
# - MIN_QUALITY_SCORE_FOR_REVIEW: quality_score floor (same 8-field
#   completeness heuristic agent_runner.py already computes) below
#   which a community submission is auto-rejected before ever reaching
#   an admin, rather than cluttering the review queue with obviously
#   incomplete extractions.
# - MAX_CONSECUTIVE_REJECTIONS: after this many consecutive rejected
#   submissions from the same user, further submissions are blocked
#   until they get one approved (self-clearing) or an admin manually
#   intervenes by approving/adjusting one of their submissions.
# - SMTP_* / ADMIN_NOTIFICATION_EMAILS / FRONTEND_BASE_URL: optional
#   email side-channel for notifications (see app/core/notifications.py).
#   Uses Python's stdlib smtplib -- no new dependency. If SMTP_HOST is
#   left blank (the default), email sending is skipped entirely and
#   only the in-app Notification row is written; nothing breaks.
# All existing settings are unchanged.

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
