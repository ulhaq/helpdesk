from src.helpdesk.kb_chunks import MAX_CHUNK_CHARS, ArticleChunk, split_article
from src.helpdesk.models.ticket import Ticket
from src.helpdesk.models.ticket_message import TicketMessage
from src.helpdesk.retrieval import query_terms
from src.helpdesk.services.assistant import ticket_search_query

# --- splitting articles


def test_splits_at_headings_with_a_heading_trail() -> None:
    body = (
        "Intro text.\n\n## Delivery\n\nShips fast.\n\n### Express\n\nNext day.\n\n"
        "## Returns\n\n30 days."
    )
    assert split_article("Shipping", body) == [
        ArticleChunk("Shipping", "Intro text."),
        ArticleChunk("Shipping > Delivery", "Ships fast."),
        ArticleChunk("Shipping > Delivery > Express", "Next day."),
        ArticleChunk("Shipping > Returns", "30 days."),
    ]


def test_ignores_headings_inside_code_fences() -> None:
    [chunk] = split_article("Setup", "## Config\n\n```\n# not a heading\nkey: 1\n```")
    assert chunk.heading == "Setup > Config"
    assert "# not a heading" in chunk.content


def test_long_sections_are_split_at_paragraphs() -> None:
    paragraph = ("word " * 400).strip()
    chunks = split_article("Guide", "\n\n".join([paragraph] * 3))
    assert [c.content for c in chunks] == [paragraph] * 3
    assert {c.heading for c in chunks} == {"Guide"}


def test_an_oversized_paragraph_is_split_hard() -> None:
    chunks = split_article("Guide", "x" * (MAX_CHUNK_CHARS * 2 + 10))
    assert [len(c.content) for c in chunks] == [MAX_CHUNK_CHARS, MAX_CHUNK_CHARS, 10]


def test_an_empty_article_is_found_by_its_title() -> None:
    assert split_article("Pricing", "") == [ArticleChunk("Pricing", "Pricing")]


# --- search terms


def test_query_terms_drop_stopwords_duplicates_and_punctuation() -> None:
    assert query_terms("How do I reset my Password? password_reset, café 4012 x") == [
        "reset",
        "password",
        "café",
        "4012",
    ]
    assert query_terms("Hvordan nulstiller jeg min adgangskode?") == [
        "nulstiller",
        "adgangskode",
    ]
    assert query_terms("?!") == []


def _message(body: str, author_type: str = "contact", internal: bool = False):
    return TicketMessage(body=body, author_type=author_type, is_internal=internal)


def test_ticket_query_uses_the_latest_customer_message() -> None:
    ticket = Ticket(subject="Login trouble")
    messages = [
        _message("First question"),
        _message("Agent answer", "agent"),
        _message("Still broken"),
        _message("Looks like SSO", "agent", internal=True),
    ]
    assert ticket_search_query(ticket, messages) == "Login trouble\nStill broken"


def test_ticket_query_without_customer_messages() -> None:
    ticket = Ticket(subject="Login trouble")
    messages = [
        _message("Private note", "agent", internal=True),
        _message("Customer called: cannot log in", "agent"),
    ]
    assert ticket_search_query(ticket, messages) == (
        "Login trouble\nCustomer called: cannot log in"
    )
    assert ticket_search_query(ticket, []) == "Login trouble"
