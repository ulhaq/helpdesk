"""Helpdesk extension of the platform repository manager.

Product services and routers depend on this subclass instead of the platform
``RepositoryManager`` so the platform stays free of product repositories.
Hook handlers that receive a platform manager can wrap its session via
``HelpdeskRepositoryManager(repos.db)`` to join the same transaction.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.repositories.agent import AgentRepository
from src.helpdesk.repositories.contact import ContactRepository
from src.helpdesk.repositories.kb import KbArticleRepository, KbCategoryRepository
from src.helpdesk.repositories.support_site import SupportSiteRepository
from src.helpdesk.repositories.ticket import TicketRepository
from src.helpdesk.repositories.ticket_message import TicketMessageRepository
from src.platform.core.database import get_db
from src.platform.repositories.repository_manager import RepositoryManager


class HelpdeskRepositoryManager(RepositoryManager):
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
        super().__init__(db)
        self._contact: ContactRepository | None = None
        self._ticket: TicketRepository | None = None
        self._ticket_message: TicketMessageRepository | None = None
        self._support_site: SupportSiteRepository | None = None
        self._agent: AgentRepository | None = None
        self._kb_category: KbCategoryRepository | None = None
        self._kb_article: KbArticleRepository | None = None

    @property
    def contact(self) -> ContactRepository:
        if self._contact is None:
            self._contact = ContactRepository(self.db)
        return self._contact

    @property
    def ticket(self) -> TicketRepository:
        if self._ticket is None:
            self._ticket = TicketRepository(self.db)
        return self._ticket

    @property
    def ticket_message(self) -> TicketMessageRepository:
        if self._ticket_message is None:
            self._ticket_message = TicketMessageRepository(self.db)
        return self._ticket_message

    @property
    def support_site(self) -> SupportSiteRepository:
        if self._support_site is None:
            self._support_site = SupportSiteRepository(self.db)
        return self._support_site

    @property
    def agent(self) -> AgentRepository:
        if self._agent is None:
            self._agent = AgentRepository(self.db)
        return self._agent

    @property
    def kb_category(self) -> KbCategoryRepository:
        if self._kb_category is None:
            self._kb_category = KbCategoryRepository(self.db)
        return self._kb_category

    @property
    def kb_article(self) -> KbArticleRepository:
        if self._kb_article is None:
            self._kb_article = KbArticleRepository(self.db)
        return self._kb_article
