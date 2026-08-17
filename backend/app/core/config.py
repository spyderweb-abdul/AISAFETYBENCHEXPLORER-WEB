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

    class Config:
        env_file = ".env"


settings = Settings()
