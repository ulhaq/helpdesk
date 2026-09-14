"""Text extraction for internal knowledge uploads.

Supported: plain text (.txt), Markdown (.md), PDF with a text layer (.pdf) and
Word (.docx). Word headings become Markdown headings, so a document is split
at its own sections. Scanned PDFs have no text layer and come out empty - OCR
is out of scope.
"""

import io
import re
from pathlib import PurePath

from docx import Document as open_docx
from fastapi import status
from pypdf import PdfReader

from src.helpdesk.enums import HelpdeskErrorCode, TextFormat
from src.helpdesk.kb_chunks import looks_like_markdown
from src.platform.core.exceptions import ClientException

SUPPORTED_EXTENSIONS = (".txt", ".md", ".markdown", ".pdf", ".docx")

_MARKDOWN_EXTENSIONS = (".md", ".markdown")
_WORD_HEADING = re.compile(r"^Heading ([1-6])$")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_BLANK_LINES = re.compile(r"\n{3,}")


def extract_text(filename: str, data: bytes) -> tuple[str, TextFormat]:
    """The file's text and whether to split it as Markdown. The text may be
    empty; callers decide what that means."""
    extension = PurePath(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ClientException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. [{extension=}]",
            error_code=HelpdeskErrorCode.UNSUPPORTED_FILE_TYPE,
        )
    try:
        if extension == ".pdf":
            text = _pdf_text(data)
        elif extension == ".docx":
            text = _docx_text(data)
        else:
            text = _decode(data)
    except Exception as exc:  # parsers raise many exception types on bad files
        raise ClientException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Could not read the file. [{extension=}]",
            error_code=HelpdeskErrorCode.FILE_UNREADABLE,
        ) from exc

    text = normalize_text(text)
    if extension in _MARKDOWN_EXTENSIONS or looks_like_markdown(text):
        return text, TextFormat.MARKDOWN
    return text, TextFormat.PLAIN


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = _TRAILING_SPACE.sub("\n", text)
    return _BLANK_LINES.sub("\n\n", text).strip()


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        # Many PDFs are "encrypted" with an empty user password.
        reader.decrypt("")
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _docx_text(data: bytes) -> str:
    document = open_docx(io.BytesIO(data))
    blocks: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style.name if paragraph.style is not None else None
        heading = _WORD_HEADING.match(style or "")
        blocks.append(f"{'#' * int(heading.group(1))} {text}" if heading else text)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                blocks.append(" | ".join(cells))
    return "\n\n".join(blocks)
