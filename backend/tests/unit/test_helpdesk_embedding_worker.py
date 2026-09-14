from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.embeddings import EMBEDDING_DIMENSIONS, InputType
from src.helpdesk.models.knowledge import KnowledgeChunk, KnowledgeDocument
from src.helpdesk.worker import embed_pending_chunks
from tests.conftest import TestSessionLocal


class RecordingEmbedder:
    def __init__(self, model: str = "model-a") -> None:
        self._model = model
        self.calls: list[tuple[list[str], InputType]] = []

    @property
    def model(self) -> str:
        return self._model

    async def embed(
        self, texts: Sequence[str], input_type: InputType
    ) -> list[list[float]]:
        self.calls.append((list(texts), input_type))
        return [[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1) for _ in texts]


async def _document(
    session: AsyncSession, organization_id: int, title: str, deleted: bool = False
) -> None:
    now = datetime.now(UTC)
    document = KnowledgeDocument(
        organization_id=organization_id,
        title=title,
        source="text",
        format="plain",
        text=f"{title} body",
        created_at=now,
        updated_at=now,
        deleted_at=now if deleted else None,
    )
    session.add(document)
    await session.flush()
    session.add(
        KnowledgeChunk(
            organization_id=organization_id,
            document_id=document.id,
            position=0,
            heading=title,
            content=f"{title} body",
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()


async def _embedded_by() -> dict[str, str | None]:
    async with TestSessionLocal() as session:
        rs = await session.execute(
            select(KnowledgeChunk.heading, KnowledgeChunk.embedding_model)
        )
        return dict(rs.tuples().all())


async def test_embeds_pending_chunks_of_every_organization_in_batches() -> None:
    async with TestSessionLocal() as session:
        await _document(session, 1, "Refunds")
        await _document(session, 2, "Shipping")
        await _document(session, 1, "Retired", deleted=True)
        await session.commit()
    embedder = RecordingEmbedder()

    assert await embed_pending_chunks(TestSessionLocal, embedder, batch_size=1) == 1
    assert await embed_pending_chunks(TestSessionLocal, embedder, batch_size=10) == 1
    assert await embed_pending_chunks(TestSessionLocal, embedder, batch_size=10) == 0

    assert embedder.calls == [
        (["Refunds\n\nRefunds body"], "document"),
        (["Shipping\n\nShipping body"], "document"),
    ]
    assert await _embedded_by() == {
        "Refunds": "model-a",
        "Shipping": "model-a",
        "Retired": None,
    }
    async with TestSessionLocal() as session:
        rs = await session.execute(
            select(KnowledgeChunk.embedding).where(KnowledgeChunk.heading == "Refunds")
        )
        vector = rs.scalar_one()
    assert vector is not None
    assert len(vector) == EMBEDDING_DIMENSIONS


async def test_a_model_change_re_embeds_everything() -> None:
    async with TestSessionLocal() as session:
        await _document(session, 1, "Refunds")
        await session.commit()

    assert await embed_pending_chunks(TestSessionLocal, RecordingEmbedder(), 10) == 1
    assert await embed_pending_chunks(TestSessionLocal, RecordingEmbedder(), 10) == 0
    new_model = RecordingEmbedder("model-b")
    assert await embed_pending_chunks(TestSessionLocal, new_model, 10) == 1
    assert await _embedded_by() == {"Refunds": "model-b"}
