import asyncio
from pathlib import PurePath
from typing import Annotated

from fastapi import Depends, UploadFile, status

from src.helpdesk.config import settings
from src.helpdesk.embeddings import Embedder, get_embedder
from src.helpdesk.enums import (
    HelpdeskAuditAction,
    HelpdeskErrorCode,
    KnowledgeDocumentSource,
    TextFormat,
)
from src.helpdesk.extraction import extract_text, normalize_text
from src.helpdesk.kb_chunks import (
    looks_like_markdown,
    split_markdown,
    split_plain_text,
)
from src.helpdesk.models.knowledge import KnowledgeDocument
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.retrieval import KnowledgeRetriever, RankedChunk, passage_for
from src.helpdesk.schemas.knowledge import (
    KnowledgeDocumentIn,
    KnowledgeDocumentOut,
    KnowledgeDocumentPatch,
    KnowledgeDocumentSummaryOut,
    KnowledgeSearchIn,
    KnowledgeSearchOut,
    KnowledgeSearchResultOut,
)
from src.platform.core.dependencies import authenticate
from src.platform.core.exceptions import ClientException
from src.platform.core.security import Auth
from src.platform.schemas.common import PageQueryParams, PaginatedResponse
from src.platform.services.base import BaseService

_EXCERPT_CHARS = 300


def _text_format(text: str) -> TextFormat:
    return TextFormat.MARKDOWN if looks_like_markdown(text) else TextFormat.PLAIN


def _search_result(ranked: RankedChunk, *, selected: bool) -> KnowledgeSearchResultOut:
    passage = passage_for(ranked.hit)
    excerpt = passage.text
    if len(excerpt) > _EXCERPT_CHARS:
        excerpt = excerpt[:_EXCERPT_CHARS].rstrip() + "…"
    return KnowledgeSearchResultOut(
        chunk_id=ranked.chunk.id,
        source_type=passage.source_type,
        source_id=passage.source_id,
        title=passage.title,
        slug=passage.slug,
        heading=passage.heading,
        excerpt=excerpt,
        score=round(ranked.score, 6),
        keyword_rank=ranked.keyword_rank,
        semantic_rank=ranked.semantic_rank,
        distance=None if ranked.distance is None else round(ranked.distance, 4),
        selected=selected,
    )


class KnowledgeService(BaseService):
    """Internal knowledge documents: team-only context for AI reply drafts."""

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
        embedder: Annotated[Embedder | None, Depends(get_embedder)],
    ) -> None:
        super().__init__(repos)
        organization_id = current_user.organization_id
        self.documents = repos.knowledge_document
        self.documents.set_organization_scope(organization_id)
        self.chunks = repos.knowledge_chunk
        self.chunks.set_organization_scope(organization_id)
        self.retriever = KnowledgeRetriever(repos, embedder)
        self.embedder = embedder
        self.current_user = current_user

    async def paginate_documents(
        self, params: PageQueryParams
    ) -> PaginatedResponse[KnowledgeDocumentSummaryOut]:
        items, total = await self.documents.paginate(
            sort=params.sort,
            filters=params.filters,
            page_size=params.page_size,
            page_number=params.page_number,
            search=params.search,
        )
        return PaginatedResponse(
            items=[KnowledgeDocumentSummaryOut.model_validate(item) for item in items],
            page_number=params.page_number,
            page_size=params.page_size,
            total=total,
        )

    async def get_document(self, identifier: int) -> KnowledgeDocumentOut:
        document = await self.documents.get_one(identifier)
        return KnowledgeDocumentOut.model_validate(document)

    async def create_text_document(
        self, schema_in: KnowledgeDocumentIn
    ) -> KnowledgeDocumentOut:
        text = self._checked_text(normalize_text(schema_in.text))
        document = await self.documents.create(
            organization_id=self.current_user.organization_id,
            author_id=self.current_user.id,
            title=schema_in.title,
            source=KnowledgeDocumentSource.TEXT,
            format=_text_format(text),
            text=text,
        )
        return await self._saved(
            document, HelpdeskAuditAction.KNOWLEDGE_DOCUMENT_CREATE
        )

    async def upload_document(
        self, file: UploadFile, title: str | None
    ) -> KnowledgeDocumentOut:
        max_bytes = settings.knowledge_max_upload_bytes
        data = await file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ClientException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Upload is larger than {max_bytes} bytes",
                error_code=HelpdeskErrorCode.FILE_TOO_LARGE,
            )
        filename = PurePath(file.filename or "document.txt").name[:255]
        # Parsing a PDF or Word file is CPU-bound; keep it off the event loop.
        text, text_format = await asyncio.to_thread(extract_text, filename, data)
        text = self._checked_text(text)

        document = await self.documents.create(
            organization_id=self.current_user.organization_id,
            author_id=self.current_user.id,
            title=(title or "").strip()[:255] or PurePath(filename).stem or filename,
            source=KnowledgeDocumentSource.FILE,
            filename=filename,
            content_type=(file.content_type or None) and file.content_type[:127],
            size_bytes=len(data),
            format=text_format,
            text=text,
        )
        return await self._saved(
            document, HelpdeskAuditAction.KNOWLEDGE_DOCUMENT_CREATE
        )

    async def patch_document(
        self, identifier: int, schema_in: KnowledgeDocumentPatch
    ) -> KnowledgeDocumentOut:
        document = await self.documents.get_one(identifier)
        # Both fields are required, so an explicit null is a no-op.
        changes = {
            key: value
            for key, value in schema_in.model_dump(exclude_unset=True).items()
            if value is not None
        }
        if "text" in changes:
            changes["text"] = self._checked_text(normalize_text(changes["text"]))
            if document.format != TextFormat.MARKDOWN or document.filename is None:
                changes["format"] = _text_format(changes["text"])
        if not changes:
            return KnowledgeDocumentOut.model_validate(document)

        document = await self.documents.update(document, **changes)
        return await self._saved(
            document, HelpdeskAuditAction.KNOWLEDGE_DOCUMENT_UPDATE
        )

    async def delete_document(self, identifier: int) -> None:
        document = await self.documents.get_one(identifier)
        await self.documents.delete(document)
        # The document is gone from the assistant's context right away.
        await self.chunks.replace(
            organization_id=document.organization_id,
            document_id=document.id,
            chunks=[],
        )
        await self._audit(HelpdeskAuditAction.KNOWLEDGE_DOCUMENT_DELETE, document)

    async def search(self, schema_in: KnowledgeSearchIn) -> KnowledgeSearchOut:
        """The retrieval ranking for a question - no AI request is made."""
        explanation = await self.retriever.explain(
            self.current_user.organization_id,
            schema_in.query,
            include_internal=schema_in.include_internal,
        )
        pending = (
            await self.chunks.count_pending_embeddings(self.embedder.model)
            if self.embedder is not None
            else 0
        )
        return KnowledgeSearchOut(
            terms=explanation.ranking.terms,
            sends_everything=explanation.sends_everything,
            semantic=explanation.ranking.semantic,
            max_distance=settings.ai_vector_max_distance,
            pending_embeddings=pending,
            results=[
                _search_result(
                    ranked, selected=ranked.chunk.id in explanation.selected_chunk_ids
                )
                for ranked in explanation.ranking.chunks
            ],
        )

    # --- helpers

    @staticmethod
    def _checked_text(text: str) -> str:
        if not text:
            raise ClientException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "The document has no text",
                error_code=HelpdeskErrorCode.DOCUMENT_EMPTY,
            )
        if len(text) > settings.knowledge_max_document_chars:
            raise ClientException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "The document has too much text",
                error_code=HelpdeskErrorCode.DOCUMENT_TOO_LONG,
            )
        return text

    async def _saved(
        self, document: KnowledgeDocument, action: HelpdeskAuditAction
    ) -> KnowledgeDocumentOut:
        split = (
            split_markdown
            if document.format == TextFormat.MARKDOWN
            else split_plain_text
        )
        await self.chunks.replace(
            organization_id=document.organization_id,
            document_id=document.id,
            chunks=split(document.title, document.text),
        )
        await self._audit(action, document)
        return KnowledgeDocumentOut.model_validate(document)

    async def _audit(
        self, action: HelpdeskAuditAction, document: KnowledgeDocument
    ) -> None:
        await self.log_audit(
            action,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="knowledge_document",
            resource_id=document.id,
            details={"title": document.title, "source": document.source},
        )
