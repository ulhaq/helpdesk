from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from src.helpdesk.enums import ArticleStatus
from src.platform.schemas.common import Timestamp

# Lowercase words joined by single hyphens; generated from the name or title
# when omitted.
KbSlug = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=200),
]
CategoryName = Annotated[str, Field(min_length=1, max_length=120)]
CategoryDescription = Annotated[str | None, Field(max_length=500)]
ArticleTitle = Annotated[str, Field(min_length=1, max_length=255)]
ArticleBody = Annotated[str, Field(max_length=100_000)]


class KbCategoryIn(BaseModel):
    name: CategoryName
    slug: KbSlug | None = None
    description: CategoryDescription = None
    position: int = 0


class KbCategoryPatch(BaseModel):
    name: CategoryName | None = None
    slug: KbSlug | None = None
    # null clears the description.
    description: CategoryDescription = None
    position: int | None = None


class KbCategoryOut(Timestamp):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    position: int


class KbCategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class KbArticleIn(BaseModel):
    title: ArticleTitle
    slug: KbSlug | None = None
    body: ArticleBody = ""
    category_id: int | None = None
    status: ArticleStatus = ArticleStatus.DRAFT


class KbArticlePatch(BaseModel):
    title: ArticleTitle | None = None
    slug: KbSlug | None = None
    body: ArticleBody | None = None
    # null removes the article from its category.
    category_id: int | None = None
    status: ArticleStatus | None = None


class KbArticleSummaryOut(Timestamp):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    status: ArticleStatus
    published_at: datetime | None
    category: KbCategoryRef | None


class KbArticleOut(KbArticleSummaryOut):
    body: str
    category_id: int | None
    author_id: int | None


class MarkdownPreviewIn(BaseModel):
    body: ArticleBody


class MarkdownPreviewOut(BaseModel):
    html: str


# --- public help center


class HelpCategoryOut(BaseModel):
    name: str
    slug: str
    description: str | None
    article_count: int


class HelpCategoryRef(BaseModel):
    name: str
    slug: str


class HelpArticleSummaryOut(BaseModel):
    title: str
    slug: str
    excerpt: str
    category: HelpCategoryRef | None
    updated_at: datetime


class HelpArticleOut(BaseModel):
    title: str
    slug: str
    # Rendered from Markdown with raw HTML disabled; safe to insert as-is.
    html: str
    category: HelpCategoryRef | None
    published_at: datetime | None
    updated_at: datetime


class HelpCenterOut(BaseModel):
    organization_name: str
    brand_color: str
    widget_enabled: bool
    categories: list[HelpCategoryOut]
    recent_articles: list[HelpArticleSummaryOut]


class HelpSearchOut(BaseModel):
    category: HelpCategoryRef | None
    articles: list[HelpArticleSummaryOut]
