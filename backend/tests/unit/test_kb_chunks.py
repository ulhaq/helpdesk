from itertools import pairwise

from src.helpdesk.kb_chunks import (
    MAX_CHUNK_CHARS,
    TextChunk,
    looks_like_markdown,
    split_markdown,
    split_plain_text,
)
from src.helpdesk.models.ticket import Ticket
from src.helpdesk.models.ticket_message import TicketMessage
from src.helpdesk.retrieval import query_terms
from src.helpdesk.services.assistant import ticket_search_query

# --- Markdown


def test_splits_at_headings_with_a_heading_trail() -> None:
    body = (
        "Intro text.\n\n## Delivery\n\nShips fast.\n\n### Express\n\nNext day.\n\n"
        "## Returns\n\n30 days."
    )
    assert split_markdown("Shipping", body) == [
        TextChunk("Shipping", "Intro text."),
        TextChunk("Shipping > Delivery", "Ships fast."),
        TextChunk("Shipping > Delivery > Express", "Next day."),
        TextChunk("Shipping > Returns", "30 days."),
    ]


def test_ignores_headings_inside_code_fences() -> None:
    [chunk] = split_markdown("Setup", "## Config\n\n```\n# not a heading\nkey: 1\n```")
    assert chunk.heading == "Setup > Config"
    assert "# not a heading" in chunk.content


def test_long_sections_are_split_at_paragraphs() -> None:
    paragraph = ("word " * 400).strip()
    chunks = split_markdown("Guide", "\n\n".join([paragraph] * 3))
    assert [c.content for c in chunks] == [paragraph] * 3
    assert {c.heading for c in chunks} == {"Guide"}


def test_an_oversized_paragraph_is_split_hard() -> None:
    chunks = split_markdown("Guide", "x" * (MAX_CHUNK_CHARS * 2 + 10))
    assert [len(c.content) for c in chunks] == [MAX_CHUNK_CHARS, MAX_CHUNK_CHARS, 10]


def test_an_empty_article_is_found_by_its_title() -> None:
    assert split_markdown("Pricing", "") == [TextChunk("Pricing", "Pricing")]


def test_looks_like_markdown() -> None:
    assert looks_like_markdown("Intro\n## Refunds\nWithin 30 days.")
    assert not looks_like_markdown("#hashtag, not a heading")
    assert not looks_like_markdown("Plain notes from a phone call.")


# --- plain text


def test_plain_text_windows_end_at_sentences_and_overlap() -> None:
    sentences = [f"Sentence number {n} explains one refund rule." for n in range(200)]
    chunks = split_plain_text("Refund memo", " ".join(sentences))

    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in chunks)
    assert {c.heading for c in chunks} == {"Refund memo"}
    # Windows end at a sentence, never mid-word...
    assert all(c.content.endswith(".") for c in chunks)
    # ...and neighbours overlap, so nothing falls between two windows.
    for previous, following in pairwise(chunks):
        assert following.content.split(". ")[0] in previous.content


def test_plain_text_with_only_line_breaks_splits_at_lines() -> None:
    lines = [f"Line {n}: customer called about invoice {n}" for n in range(300)]
    chunks = split_plain_text("Call notes", "\n".join(lines))

    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in chunks)
    assert all(c.content.splitlines()[-1] in lines for c in chunks)


def test_short_and_empty_plain_text() -> None:
    assert split_plain_text("Note", "  Call Bob.  ") == [TextChunk("Note", "Call Bob.")]
    assert split_plain_text("Note", "") == [TextChunk("Note", "Note")]


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
