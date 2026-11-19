"""Text helpers: ReportLab's built-in fonts only know Latin-1, so map everything else to something readable."""
import unicodedata
from xml.sax.saxutils import escape

_MAP = {"—": "-", "–": "-", "‒": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
        "•": "*", "≥": ">=", "≤": "<=", "→": "->", "↑": "up", "↓": "down", "−": "-", " ": " "}


def plain(value):
    """Latin-1 safe plain text. Accents are kept when Latin-1 has them, otherwise stripped, otherwise '?'."""
    text = "" if value is None else str(value)
    for old, new in _MAP.items():
        text = text.replace(old, new)
    out = []
    for ch in text:
        try:
            ch.encode("latin-1")
            out.append(ch)
            continue
        except UnicodeEncodeError:
            pass
        base = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode("ascii")
        out.append(base or "?")
    return "".join(out)


def t(value):
    """plain() + XML escaping, safe inside a ReportLab Paragraph."""
    return escape(plain(value))


def num(value, digits=1, suffix="", signed=False):
    """'12.3 km' style number or an en dash placeholder when the value is missing."""
    if value is None or value == "":
        return "-"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return plain(value)
    shown = f"{v:+.{digits}f}" if signed else f"{v:.{digits}f}"
    if digits and shown.rstrip("0").endswith("."):
        shown = shown.rstrip("0").rstrip(".")
    return f"{shown}{suffix}"
