"""Knowledge base retrieval for the AI assistant (the "R" in RAG).

Small help centers are sent whole: the articles fit comfortably and, being
identical across requests, are served from the prompt cache. Once the
published articles exceed `ai_full_context_max_chars`, each request gets only
the article sections that best match its query - ranked by full-text search
(`KbArticleChunkRepository.search`) - within a fixed passage and size budget.

`KbRetriever.retrieve` is the seam for better retrieval later (embeddings,
hybrid ranking): callers only ever see passages.
"""

import re
from dataclasses import dataclass

from src.helpdesk.config import settings
from src.helpdesk.enums import AiRetrievalMode
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager

_TERM = re.compile(r"[^\W_]+")
_MAX_TERMS = 24
# Words too common to say anything about which article is relevant. Search
# uses the language-neutral 'simple' text configuration (articles may be
# Danish or English), so these are dropped from the query here instead.
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


def query_terms(text: str) -> list[str]:
    """Distinct, lowercase search terms from free text, stopwords removed."""
    terms: list[str] = []
    for term in _TERM.findall(text.lower()):
        if len(term) < 2 or term in _STOPWORDS or term in terms:
            continue
        terms.append(term)
    return terms[:_MAX_TERMS]


@dataclass(frozen=True)
class KbPassage:
    article_id: int
    # The article's title and slug, shown to readers as the source.
    title: str
    slug: str
    heading: str
    text: str


@dataclass(frozen=True)
class Retrieval:
    mode: AiRetrievalMode
    passages: list[KbPassage]
    # Chunks behind the passages; empty when whole articles were sent.
    chunk_ids: list[int]

    @property
    def cacheable(self) -> bool:
        """Whole-help-center context repeats across requests; searched
        sections differ every time, so caching them only costs."""
        return self.mode == AiRetrievalMode.FULL


class KbRetriever:
    def __init__(self, repos: HelpdeskRepositoryManager) -> None:
        self.articles = repos.kb_article
        self.chunks = repos.kb_article_chunk

    async def retrieve(self, organization_id: int, query: str) -> Retrieval:
        self.articles.set_organization_scope(organization_id)
        self.chunks.set_organization_scope(organization_id)

        if await self.articles.published_chars() <= settings.ai_full_context_max_chars:
            articles = await self.articles.list_published(order="title", limit=None)
            return Retrieval(
                mode=AiRetrievalMode.FULL,
                passages=[
                    KbPassage(a.id, a.title, a.slug, heading=a.title, text=a.body)
                    for a in articles
                ],
                chunk_ids=[],
            )

        passages: list[KbPassage] = []
        chunk_ids: list[int] = []
        terms = query_terms(query)
        if not terms:
            return Retrieval(AiRetrievalMode.SEARCH, passages, chunk_ids)

        used_chars = 0
        max_passages = settings.ai_retrieval_max_passages
        for chunk, article in await self.chunks.search(terms, limit=max_passages * 3):
            size = len(chunk.heading) + len(chunk.content)
            if used_chars + size > settings.ai_retrieval_max_chars:
                # A shorter, lower-ranked section may still fit.
                continue
            used_chars += size
            chunk_ids.append(chunk.id)
            passages.append(
                KbPassage(
                    article.id,
                    article.title,
                    article.slug,
                    heading=chunk.heading,
                    text=chunk.content,
                )
            )
            if len(passages) == max_passages:
                break
        return Retrieval(AiRetrievalMode.SEARCH, passages, chunk_ids)
