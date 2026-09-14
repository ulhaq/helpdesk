"""Helpdesk product settings.

Independent settings namespace for the product: every field is read from the
environment with a `HELPDESK_` prefix (e.g. `contact_token_max_age_seconds` <-
`HELPDESK_CONTACT_TOKEN_MAX_AGE_SECONDS`).
"""

from typing import Literal

from pydantic import Field, SecretStr
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
    # Bounds on the help center context sent with each request.
    ai_max_articles: int = 200
    ai_max_article_chars: int = 400_000


settings = HelpdeskSettings()
