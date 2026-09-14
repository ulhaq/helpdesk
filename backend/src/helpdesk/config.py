"""Helpdesk product settings.

Independent settings namespace for the product: every field is read from the
environment with a `HELPDESK_` prefix (e.g. `contact_token_max_age_seconds` <-
`HELPDESK_CONTACT_TOKEN_MAX_AGE_SECONDS`).
"""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import SettingsConfigDict

from src.platform.core.config import EnvSettings


class HelpdeskSettings(EnvSettings):
    model_config = SettingsConfigDict(env_prefix="helpdesk_")

    # How long a customer's conversation link (and widget session) stays valid.
    contact_token_max_age_seconds: int = 90 * 24 * 60 * 60

    # Resolved tickets nobody reopened are closed after this many days
    # (0 turns auto-close off), checked every `auto_close_interval_seconds`.
    auto_close_resolved_after_days: int = 7
    auto_close_interval_seconds: int = 60 * 60

    # Claude-powered reply drafts and widget answers; both stay off while no
    # key is set. Read from ANTHROPIC_API_KEY (no HELPDESK_ prefix).
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias="anthropic_api_key"
    )
    ai_model: str = "claude-haiku-4-5"
    ai_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    # Knowledge base context (see src/helpdesk/retrieval.py): help centers up
    # to this size are sent whole and prompt-cached; larger ones get only the
    # best-matching article sections, within the passage and size budget.
    ai_full_context_max_chars: int = 120_000
    ai_retrieval_max_passages: int = 8
    ai_retrieval_max_chars: int = 32_000
    # Candidates taken from each ranking (full-text, semantic) before fusion,
    # and how far a semantic match may be (cosine distance: 0 identical,
    # 2 opposite). Tune the distance per model using ai_request_log.
    ai_retrieval_candidates: int = 30
    ai_vector_max_distance: float = 0.6

    # Semantic search (src/helpdesk/embeddings.py); off while no provider is
    # set. "openai_compatible" is any server with OpenAI's /embeddings API
    # (Ollama, vLLM, llama.cpp, TEI, ...). The model must return 1024
    # dimensions; changing the model re-embeds everything.
    embedding_provider: Literal["openai_compatible", "voyage"] | None = None
    embedding_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: SecretStr | None = None
    # Prepended to search queries only. Instruction-tuned embedding models
    # (e.g. Qwen3-Embedding) retrieve better with a task instruction.
    embedding_query_prefix: str = ""
    embedding_batch_size: int = 32
    embedding_interval_seconds: int = 15

    # Internal knowledge documents.
    knowledge_max_upload_bytes: int = 10 * 1024 * 1024
    knowledge_max_document_chars: int = 500_000

    @field_validator("embedding_provider", mode="before")
    @classmethod
    def _empty_provider_is_none(cls, value: object) -> object:
        return None if value == "" else value

    # AI request logs (query, retrieved sections, outcome) contain customer
    # text; the worker deletes them after this many days (0 keeps them).
    ai_request_log_retention_days: int = 90


settings = HelpdeskSettings()
