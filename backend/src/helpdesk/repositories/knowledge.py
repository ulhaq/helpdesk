from collections.abc import Sequence
from datetime import UTC, datetime
from math import sqrt
from typing import ClassVar

from sqlalchemy import (
    Select,
    and_,
    bindparam,
    delete,
    func,
    literal_column,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.enums import ArticleStatus
from src.helpdesk.kb_chunks import TextChunk
from src.helpdesk.models.kb import KbArticle
from src.helpdesk.models.knowledge import KnowledgeChunk, KnowledgeDocument
from src.platform.core.exceptions import UnscopedQueryError
from src.platform.repositories.base import OrganizationScopedRepository

# Full-text document for a chunk: heading words outrank body words. Must stay
# identical to the `ix_knowledge_chunk_search` index expression, or Postgres
# can't use the index. 'simple' has no stemming or stopwords, so it works for
# Danish and English alike; query terms use prefix matching instead.
_SEARCH_VECTOR = (
    "setweight(to_tsvector('simple'::regconfig, knowledge_chunk.heading), "
    "'A'::\"char\") || "
    "setweight(to_tsvector('simple'::regconfig, knowledge_chunk.content), "
    "'B'::\"char\")"
)

# A chunk with its source: exactly one of the article and document is set.
KnowledgeHit = tuple[KnowledgeChunk, KbArticle | None, KnowledgeDocument | None]


class KnowledgeDocumentRepository(OrganizationScopedRepository[KnowledgeDocument]):
    search_fields: ClassVar[list[str]] = ["title", "filename"]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(KnowledgeDocument, db)

    async def list_active(self) -> Sequence[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).order_by(
            KnowledgeDocument.title, KnowledgeDocument.id
        )
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        rs = await self.db.execute(stmt)
        return rs.scalars().all()

    async def active_chars(self) -> int:
        """Total title and text length of the active documents."""
        stmt = select(
            func.coalesce(
                func.sum(
                    func.length(KnowledgeDocument.title)
                    + func.length(KnowledgeDocument.text)
                ),
                0,
            )
        )
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        rs = await self.db.execute(stmt)
        return int(rs.scalar_one())


class KnowledgeChunkRepository(OrganizationScopedRepository[KnowledgeChunk]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(KnowledgeChunk, db)

    async def replace(
        self,
        *,
        organization_id: int,
        chunks: Sequence[TextChunk],
        article_id: int | None = None,
        document_id: int | None = None,
    ) -> None:
        """Replace one source's chunks. New chunks have no embedding until the
        embedding worker picks them up."""
        if (article_id is None) == (document_id is None):
            raise ValueError("Pass exactly one of article_id and document_id.")
        source = (
            KnowledgeChunk.article_id == article_id
            if article_id is not None
            else KnowledgeChunk.document_id == document_id
        )
        existing = self._apply_organization_scope(
            select(KnowledgeChunk.id).where(source)
        )
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.id.in_(existing))
        )
        now = datetime.now(UTC)
        self.db.add_all(
            [
                KnowledgeChunk(
                    organization_id=organization_id,
                    article_id=article_id,
                    document_id=document_id,
                    position=position,
                    heading=chunk.heading,
                    content=chunk.content,
                    created_at=now,
                    updated_at=now,
                )
                for position, chunk in enumerate(chunks)
            ]
        )
        await self.save()

    async def search(
        self, terms: Sequence[str], *, limit: int, include_internal: bool
    ) -> list[KnowledgeHit]:
        """Chunks matching any of `terms`, best match first."""
        stmt = self._hits(include_internal=include_internal)
        if self._is_postgres():
            return await self._search_full_text(stmt, terms, limit)
        return await self._search_substrings(stmt, terms, limit)

    async def nearest(
        self,
        vector: Sequence[float],
        *,
        model: str,
        limit: int,
        max_distance: float,
        include_internal: bool,
    ) -> list[tuple[KnowledgeHit, float]]:
        """Chunks embedded by `model` closest in meaning to `vector`, with
        their cosine distance (0 identical, 2 opposite) up to `max_distance`."""
        stmt = self._hits(include_internal=include_internal).where(
            KnowledgeChunk.embedding_model == model,
            KnowledgeChunk.embedding.is_not(None),
        )
        if self._is_postgres():
            # The HNSW index hands back a fixed number of neighbours before
            # the organization and source filters apply; iterative scans keep
            # going until `limit` rows pass them (pgvector >= 0.8).
            await self.db.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
            distance = KnowledgeChunk.embedding.cosine_distance(list(vector))
            stmt = (
                stmt.add_columns(distance)
                .where(distance <= max_distance)
                .order_by(distance, KnowledgeChunk.id)
                .limit(limit)
            )
            rs = await self.db.execute(stmt)
            return [
                ((chunk, article, document), float(chunk_distance))
                for chunk, article, document, chunk_distance in rs.tuples().all()
            ]

        # Portable fallback for SQLite (tests): cosine distance in Python.
        rs = await self.db.execute(stmt.add_columns(KnowledgeChunk.embedding))
        scored: list[tuple[float, int, KnowledgeHit]] = []
        for chunk, article, document, embedding in rs.tuples().all():
            distance = 1 - _cosine_similarity(vector, embedding)
            if distance <= max_distance:
                scored.append((distance, chunk.id, (chunk, article, document)))
        scored.sort(key=lambda item: (item[0], item[1]))
        return [(hit, distance) for distance, _, hit in scored[:limit]]

    async def pending_embeddings(
        self, model: str, *, limit: int
    ) -> Sequence[KnowledgeChunk]:
        """Chunks of live sources not yet embedded by `model`, oldest first.
        Draft articles are embedded too, so publishing needs no extra step."""
        stmt = self._pending(select(KnowledgeChunk), model)
        stmt = self._apply_organization_scope(stmt.order_by(KnowledgeChunk.id))
        rs = await self.db.execute(stmt.limit(limit))
        return rs.scalars().all()

    async def count_pending_embeddings(self, model: str) -> int:
        stmt = self._pending(select(func.count(KnowledgeChunk.id)), model)
        rs = await self.db.execute(self._apply_organization_scope(stmt))
        return int(rs.scalar_one())

    @staticmethod
    def _pending(stmt: Select, model: str) -> Select:
        return (
            stmt.select_from(KnowledgeChunk)
            .outerjoin(KbArticle, KbArticle.id == KnowledgeChunk.article_id)
            .outerjoin(
                KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id
            )
            .where(
                or_(
                    KnowledgeChunk.embedding_model.is_(None),
                    KnowledgeChunk.embedding_model != model,
                ),
                or_(
                    and_(KbArticle.id.is_not(None), KbArticle.deleted_at.is_(None)),
                    and_(
                        KnowledgeDocument.id.is_not(None),
                        KnowledgeDocument.deleted_at.is_(None),
                    ),
                ),
            )
        )

    async def store_embeddings(
        self, embeddings: dict[int, list[float]], *, model: str
    ) -> None:
        """Save vectors by chunk id. Chunks replaced in the meantime no longer
        exist, so their stale vectors are simply dropped."""
        if not embeddings:
            return
        stmt = update(KnowledgeChunk).where(KnowledgeChunk.id == bindparam("chunk_id"))
        if self._organization_id is not None:
            stmt = stmt.where(KnowledgeChunk.organization_id == self._organization_id)
        elif not self._allow_unscoped:
            raise UnscopedQueryError(
                "store_embeddings needs an organization scope or `.unscoped`."
            )
        stmt = stmt.values(embedding=bindparam("vector"), embedding_model=model)
        # A Core executemany: the ORM would treat a list of parameters as a
        # bulk update by primary key, which can't carry this WHERE clause.
        connection = await self.db.connection()
        await connection.execute(
            stmt,
            [
                {"chunk_id": chunk_id, "vector": vector}
                for chunk_id, vector in embeddings.items()
            ],
        )

    def _is_postgres(self) -> bool:
        return self.db.get_bind().dialect.name == "postgresql"

    def _hits(self, *, include_internal: bool) -> Select:
        """Chunks joined to their source, limited to published, active
        articles - plus active internal documents when `include_internal`."""
        sources = [
            and_(
                KbArticle.status == ArticleStatus.PUBLISHED,
                KbArticle.deleted_at.is_(None),
            )
        ]
        if include_internal:
            sources.append(
                and_(
                    KnowledgeDocument.id.is_not(None),
                    KnowledgeDocument.deleted_at.is_(None),
                )
            )
        stmt = (
            select(KnowledgeChunk, KbArticle, KnowledgeDocument)
            .outerjoin(
                KbArticle,
                and_(
                    KbArticle.id == KnowledgeChunk.article_id,
                    KbArticle.organization_id == KnowledgeChunk.organization_id,
                ),
            )
            .outerjoin(
                KnowledgeDocument,
                and_(
                    KnowledgeDocument.id == KnowledgeChunk.document_id,
                    KnowledgeDocument.organization_id == KnowledgeChunk.organization_id,
                ),
            )
            .where(or_(*sources))
        )
        return self._apply_organization_scope(stmt)

    async def _search_full_text(
        self, stmt: Select, terms: Sequence[str], limit: int
    ) -> list[KnowledgeHit]:
        vector = literal_column(_SEARCH_VECTOR)
        # Terms are letters and digits only (see `retrieval.query_terms`), so
        # they're safe inside tsquery syntax. Prefix matching (`:*`) stands in
        # for stemming: "invoice" also finds "invoices".
        query = func.to_tsquery(
            literal_column("'simple'::regconfig"),
            " | ".join(f"{term}:*" for term in terms),
        )
        # Normalization 1 divides by 1 + log(length): long sections don't win
        # just by repeating words.
        rank = func.ts_rank(vector, query, 1)
        stmt = (
            stmt.where(vector.op("@@")(query))
            .order_by(rank.desc(), KnowledgeChunk.id)
            .limit(limit)
        )
        rs = await self.db.execute(stmt)
        return [
            (chunk, article, document) for chunk, article, document in rs.tuples().all()
        ]

    async def _search_substrings(
        self, stmt: Select, terms: Sequence[str], limit: int
    ) -> list[KnowledgeHit]:
        """Portable fallback for databases without full-text search (the
        SQLite test suite): substring matches, ranked like the Postgres
        weights - a heading hit counts double."""
        stmt = stmt.where(
            or_(
                *(
                    field.ilike(f"%{term}%")
                    for term in terms
                    for field in (KnowledgeChunk.heading, KnowledgeChunk.content)
                )
            )
        )
        rs = await self.db.execute(stmt)
        rows: list[KnowledgeHit] = [
            (chunk, article, document) for chunk, article, document in rs.tuples().all()
        ]

        def score(chunk: KnowledgeChunk) -> int:
            heading, content = chunk.heading.lower(), chunk.content.lower()
            return sum(2 * heading.count(t) + content.count(t) for t in terms)

        rows.sort(key=lambda row: (-score(row[0]), row[0].id))
        return rows[:limit]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norms = sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b))
    return dot / norms if norms else 0.0
