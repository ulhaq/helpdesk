from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# 3-64 lowercase letters, digits and inner hyphens: it is part of public URLs.
SupportSlug = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
]
BrandColor = Annotated[
    str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$", to_lower=True)
]


class SupportSiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    brand_color: str
    greeting: str | None
    widget_enabled: bool
    help_center_enabled: bool
    updated_at: datetime


class SupportSitePatch(BaseModel):
    slug: SupportSlug | None = None
    brand_color: BrandColor | None = None
    # null clears the greeting; the widget then shows its default copy.
    greeting: Annotated[str | None, Field(max_length=255)] = None
    widget_enabled: bool | None = None
    help_center_enabled: bool | None = None
