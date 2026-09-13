"""Helpdesk product settings.

Independent settings namespace for the product: every field is read from the
environment with a `HELPDESK_` prefix (e.g. `contact_token_max_age_seconds` <-
`HELPDESK_CONTACT_TOKEN_MAX_AGE_SECONDS`).
"""

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


settings = HelpdeskSettings()
