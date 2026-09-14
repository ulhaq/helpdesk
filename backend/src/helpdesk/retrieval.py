"""Knowledge retrieval for the AI assistant (the "R" in RAG).

Sources are the published help center articles and - for agent-facing
features only - internal knowledge documents.

- With an embedding model configured, every request gets only the
  best-matching sections, within a passage and size budget. Sections are
  ranked by full-text search and by semantic similarity; the two rankings are
  merged with reciprocal rank fusion. Keyword search is precise on exact terms
  (error codes, plan names); embeddings catch paraphrases and loosely written
  internal text. If the model fails for a request, that request still
  searches, by keywords only.
- Without an embedding model, keyword search alone misses paraphrases, so
  small knowledge bases are sent whole instead (served from the prompt cache);
  larger ones are searched by keywords.

`KnowledgeRetriever.retrieve` is the entry point for AI requests; `explain`
shows the same ranking without calling Claude (the knowledge search tester).
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.helpdesk.config import settings
from src.helpdesk.embeddings import Embedder, EmbeddingError
from src.helpdesk.enums import (
    AiRetrievalMode,
    KnowledgeSourceType,
    SemanticSearchStatus,
)
from src.helpdesk.models.knowledge import KnowledgeChunk
from src.helpdesk.repositories.knowledge import KnowledgeHit
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager

log = logging.getLogger(__name__)

_TERM = re.compile(r"[^\W_]+")
_MAX_TERMS = 24
# Words too common to say anything about which section is relevant. Search
# uses the language-neutral 'simple' text configuration (content may be Danish
# or English), so these are dropped from the query here instead.
_STOPWORDS = frozenset(
    # English
    "a an and are as at be been but by can could did do does doing for from "
    "had has have having hello hi how i if in into is it its just me my no not "
    "of on or our please so than that the their them then there these they "
    "this to too us was we were what when where which who why will with would "
    "you your "
    # Danish
    "af alle at bare da de dem den denne der det dette dig din dit du efter "
    "eller en er et for fra gerne har hej hvad hvis hvor hvordan hvorfor i ikke "
    "jeg jer kan man med mig min mit mine skal som til ud var vi vil være".split()
)
# Reciprocal rank fusion constant. 60 is the customary value: it keeps one
# ranking's top hit from outweighing agreement between both rankings.
_RRF_K = 60


def query_terms(text: str) -> list[str]:
    """Distinct, lowercase search terms from free text, stopwords removed."""
    terms: list[str] = []
    for term in _TERM.findall(text.lower()):
        if len(term) < 2 or term in _STOPWORDS or term in terms:
            continue
        terms.append(term)
    return terms[:_MAX_TERMS]


@dataclass(frozen=True)
class RankedChunk:
    hit: KnowledgeHit
    # Reciprocal rank fusion score; higher ranks first.
    score: float
    keyword_rank: int | None
    semantic_rank: int | None
    # Cosine distance to the query, when semantic search found the chunk.
    distance: float | None

    @property
    def chunk(self) -> KnowledgeChunk:
        return self.hit[0]


def fuse_rankings(
    keyword: Sequence[KnowledgeHit],
    semantic: Sequence[tuple[KnowledgeHit, float]],
) -> list[RankedChunk]:
    """Merge the full-text and semantic rankings by reciprocal rank fusion: a
    chunk scores 1 / (k + rank) in each ranking it appears in."""
    hits: dict[int, KnowledgeHit] = {}
    keyword_ranks: dict[int, int] = {}
    semantic_ranks: dict[int, int] = {}
    distances: dict[int, float] = {}
    for rank, hit in enumerate(keyword, start=1):
        hits.setdefault(hit[0].id, hit)
        keyword_ranks[hit[0].id] = rank
    for rank, (hit, distance) in enumerate(semantic, start=1):
        hits.setdefault(hit[0].id, hit)
        semantic_ranks[hit[0].id] = rank
        distances[hit[0].id] = distance

    def score(chunk_id: int) -> float:
        ranks = (keyword_ranks.get(chunk_id), semantic_ranks.get(chunk_id))
        return sum(1 / (_RRF_K + rank) for rank in ranks if rank is not None)

    ranked = [
        RankedChunk(
            hit=hit,
            score=score(chunk_id),
            keyword_rank=keyword_ranks.get(chunk_id),
            semantic_rank=semantic_ranks.get(chunk_id),
            distance=distances.get(chunk_id),
        )
        for chunk_id, hit in hits.items()
    ]
    ranked.sort(key=lambda item: (-item.score, item.chunk.id))
    return ranked


@dataclass(frozen=True)
class Ranking:
    terms: list[str]
    chunks: list[RankedChunk]
    semantic: SemanticSearchStatus


@dataclass(frozen=True)
class KnowledgePassage:
    source_type: KnowledgeSourceType
    source_id: int
    title: str
    # Help center slug; None for internal documents, which have no public page.
    slug: str | None
    heading: str
    text: str

    @property
    def internal(self) -> bool:
        return self.source_type == KnowledgeSourceType.DOCUMENT


@dataclass(frozen=True)
class Retrieval:
    mode: AiRetrievalMode
    passages: list[KnowledgePassage]
    # Chunks behind the passages; empty when whole sources were sent.
    chunk_ids: list[int]

    @property
    def cacheable(self) -> bool:
        """Whole-knowledge-base context repeats across requests; searched
        sections differ every time, so caching them only costs."""
        return self.mode == AiRetrievalMode.FULL


@dataclass(frozen=True)
class SearchExplanation:
    ranking: Ranking
    # Whether a real request sends the whole knowledge base instead of the
    # ranked sections.
    sends_everything: bool
    # Chunks a search would pass on to Claude, within the budget.
    selected_chunk_ids: set[int]


class KnowledgeRetriever:
    def __init__(
        self, repos: HelpdeskRepositoryManager, embedder: Embedder | None
    ) -> None:
        self.articles = repos.kb_article
        self.documents = repos.knowledge_document
        self.chunks = repos.knowledge_chunk
        self.embedder = embedder

    async def retrieve(
        self, organization_id: int, query: str, *, include_internal: bool
    ) -> Retrieval:
        """Passages for `query`. `include_internal` adds internal documents -
        only ever for agent-facing features."""
        self._scope(organization_id)
        if await self._fits_whole(include_internal=include_internal):
            return await self._everything(include_internal=include_internal)

        ranking = await self._rank(query, include_internal=include_internal)
        selected = _within_budget(ranking.chunks)
        mode = (
            AiRetrievalMode.HYBRID
            if ranking.semantic == SemanticSearchStatus.OK
            else AiRetrievalMode.SEARCH
        )
        return Retrieval(
            mode,
            [passage_for(ranked.hit) for ranked in selected],
            [ranked.chunk.id for ranked in selected],
        )

    async def explain(
        self, organization_id: int, query: str, *, include_internal: bool
    ) -> SearchExplanation:
        """How search ranks `query`, without calling Claude. Always searches,
        and reports whether a real request would send everything instead."""
        self._scope(organization_id)
        sends_everything = await self._fits_whole(include_internal=include_internal)
        ranking = await self._rank(query, include_internal=include_internal)
        return SearchExplanation(
            ranking=ranking,
            sends_everything=sends_everything,
            selected_chunk_ids={r.chunk.id for r in _within_budget(ranking.chunks)},
        )

    def _scope(self, organization_id: int) -> None:
        self.articles.set_organization_scope(organization_id)
        self.documents.set_organization_scope(organization_id)
        self.chunks.set_organization_scope(organization_id)

    async def _fits_whole(self, *, include_internal: bool) -> bool:
        """Whether to send the whole knowledge base instead of searching: only
        without an embedding model. With one, search is reliable enough, and
        sending less is cheaper, faster and exposes less internal text."""
        if self.embedder is not None:
            return False
        size = await self.articles.published_chars()
        if include_internal:
            size += await self.documents.active_chars()
        return size <= settings.ai_full_context_max_chars

    async def _everything(self, *, include_internal: bool) -> Retrieval:
        passages = [
            KnowledgePassage(
                KnowledgeSourceType.ARTICLE,
                article.id,
                article.title,
                article.slug,
                heading=article.title,
                text=article.body,
            )
            for article in await self.articles.list_published(order="title", limit=None)
        ]
        if include_internal:
            passages += [
                KnowledgePassage(
                    KnowledgeSourceType.DOCUMENT,
                    document.id,
                    document.title,
                    None,
                    heading=document.title,
                    text=document.text,
                )
                for document in await self.documents.list_active()
            ]
        return Retrieval(AiRetrievalMode.FULL, passages, [])

    async def _rank(self, query: str, *, include_internal: bool) -> Ranking:
        limit = settings.ai_retrieval_candidates
        terms = query_terms(query)
        keyword = (
            await self.chunks.search(
                terms, limit=limit, include_internal=include_internal
            )
            if terms
            else []
        )

        semantic: list[tuple[KnowledgeHit, float]] = []
        status = SemanticSearchStatus.OFF
        if self.embedder is not None and query.strip():
            try:
                [vector] = await self.embedder.embed([query], "query")
            except EmbeddingError as exc:
                log.warning(
                    "Semantic search unavailable, using full-text search: %s", exc
                )
                status = SemanticSearchStatus.UNAVAILABLE
            else:
                status = SemanticSearchStatus.OK
                semantic = await self.chunks.nearest(
                    vector,
                    model=self.embedder.model,
                    limit=limit,
                    max_distance=settings.ai_vector_max_distance,
                    include_internal=include_internal,
                )
        return Ranking(terms, fuse_rankings(keyword, semantic), status)


def _within_budget(ranked: Sequence[RankedChunk]) -> list[RankedChunk]:
    selected: list[RankedChunk] = []
    used_chars = 0
    for item in ranked:
        size = len(item.chunk.heading) + len(item.chunk.content)
        if used_chars + size > settings.ai_retrieval_max_chars:
            # A shorter, lower-ranked section may still fit.
            continue
        used_chars += size
        selected.append(item)
        if len(selected) == settings.ai_retrieval_max_passages:
            break
    return selected


def passage_for(hit: KnowledgeHit) -> KnowledgePassage:
    chunk, article, document = hit
    if article is not None:
        return KnowledgePassage(
            KnowledgeSourceType.ARTICLE,
            article.id,
            article.title,
            article.slug,
            heading=chunk.heading,
            text=chunk.content,
        )
    if document is None:
        raise ValueError(f"Knowledge chunk has no source. [chunk_id={chunk.id}]")
    return KnowledgePassage(
        KnowledgeSourceType.DOCUMENT,
        document.id,
        document.title,
        None,
        heading=chunk.heading,
        text=chunk.content,
    )
