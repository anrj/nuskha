"""Georgian text handling. Pure functions, no I/O: easy to test and reuse in the desktop app."""
from .normalize import normalize, georgian_ratio, is_mostly_latin
from .legacy import from_legacy_font, fix_legacy_text, fix_keyboard_layout
from .translit import latin_to_georgian, query_variants

__all__ = [
    "normalize", "georgian_ratio", "is_mostly_latin",
    "from_legacy_font", "fix_legacy_text", "fix_keyboard_layout",
    "latin_to_georgian", "query_variants",
]
