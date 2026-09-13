import re
import unicodedata

# Letters NFKD cannot decompose into ASCII, spelled the way Danish URLs do.
_TRANSLITERATE = str.maketrans(
    {"æ": "ae", "ø": "oe", "å": "aa", "Æ": "Ae", "Ø": "Oe", "Å": "Aa", "ß": "ss"}
)
_UNSAFE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, max_length: int = 80, fallback: str = "item") -> str:
    """Lowercase ASCII words joined by hyphens, for use in public URLs."""
    ascii_text = (
        unicodedata.normalize("NFKD", text.translate(_TRANSLITERATE))
        .encode("ascii", "ignore")
        .decode()
    )
    slug = _UNSAFE.sub("-", ascii_text.lower()).strip("-")
    return slug[:max_length].strip("-") or fallback
