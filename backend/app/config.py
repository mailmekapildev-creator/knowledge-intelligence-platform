"""
Centralized configuration. MOCK_MODE=true (default) lets the entire pipeline run
deterministically with zero external dependencies and zero API cost -- this is what
lets a reviewer clone the repo and see it work in under five minutes.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Mode ---
    mock_mode: bool = True

    # --- Auth ---
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    # --- LLM ---
    anthropic_api_key: str = ""
    llm_model_primary: str = "claude-sonnet-5"
    llm_model_fallback: str = "claude-haiku-4-5-20251001"
    llm_timeout_seconds: float = 15.0
    llm_max_retries: int = 2

    # --- Embeddings ---
    embedding_dim: int = 384
    embedding_batch_size: int = 32

    # --- Retrieval ---
    hybrid_vector_weight: float = 0.6
    hybrid_bm25_weight: float = 0.4
    retrieval_top_k_candidates: int = 50
    rerank_top_k: int = 6

    # --- Rate limiting ---
    rate_limit_requests_per_minute: int = 60

    # --- Infra ---
    database_url: str = "postgresql+asyncpg://kip:kip@localhost:5432/kip"
    redis_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
