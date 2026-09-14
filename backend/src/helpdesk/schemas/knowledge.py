from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.helpdesk.config import settings
from src.helpdesk.enums import (
    KnowledgeDocumentSource,
    KnowledgeSourceType,
    SemanticSearchStatus,
    TextFormat,
)
from src.platform.schemas.common import Timestamp

DocumentTitle = Annotated[str, Field(min_length=1, max_length=255)]
DocumentText = Annotated[
    str, Field(min_length=1, max_length=settings.knowledge_max_document_chars)
]


class KnowledgeDocumentIn(BaseModel):
    title: DocumentTitle
    text: DocumentText


class KnowledgeDocumentPatch(BaseModel):
    title: DocumentTitle | None = None
    # Editable for uploads too, e.g. to clean up badly extracted PDF text.
    text: DocumentText | None = None


class KnowledgeDocumentSummaryOut(Timestamp):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source: KnowledgeDocumentSource
    filename: str | None
    size_bytes: int | None
    format: TextFormat


class KnowledgeDocumentOut(KnowledgeDocumentSummaryOut):
    author_id: int | None
    content_type: str | None
    text: str


class KnowledgeSearchIn(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=2_000)]
    # False searches what widget answers may use: published articles only.
    include_internal: bool = True


class KnowledgeSearchResultOut(BaseModel):
    chunk_id: int
    source_type: KnowledgeSourceType
    source_id: int
    title: str
    # Help center slug; null for internal documents.
    slug: str | None
    heading: str
    excerpt: str
    # Reciprocal rank fusion score; results are ordered by it.
    score: float
    keyword_rank: int | None
    semantic_rank: int | None
    # Cosine distance to the question: 0 identical, 2 opposite.
    distance: float | None
    # Whether a searched AI request would pass this section on to Claude.
    selected: bool


class KnowledgeSearchOut(BaseModel):
    terms: list[str]
    # True while the knowledge base is small enough that AI requests receive
    # all of it; the results then show what search picks once it grows.
    sends_everything: bool
    semantic: SemanticSearchStatus
    max_distance: float
    # Sections still waiting for the embedding worker (keyword search only).
    pending_embeddings: int
    results: list[KnowledgeSearchResultOut]
