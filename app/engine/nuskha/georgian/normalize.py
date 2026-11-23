"""Normalization applied identically to document text and to queries."""
import re
import unicodedata

GEORGIAN = re.compile(r"[ა-ჿᲐ-Ჿⴀ-⴯]")
LATIN = re.compile(r"[A-Za-z]")
LETTER = re.compile(r"[^\W\d_]")

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_QUOTES = str.maketrans({"„": '"', "“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "`": "'"})
# Hyphenated line breaks in PDFs: "ხელშეკრუ-\nლება" -> "ხელშეკრულება"
_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFC, drop invisible chars, unify quotes, join hyphen breaks, casefold, collapse spaces.

    casefold() also maps Mtavruli capitals (U+1C90..) to Mkhedruli, so "ᲮᲔᲚᲨᲔᲙᲠᲣᲚᲔᲑᲐ" == "ხელშეკრულება".
    """
    text = unicodedata.normalize("NFC", text).translate(_INVISIBLE).translate(_QUOTES)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    return _WS.sub(" ", text.casefold()).strip()


def georgian_ratio(text: str) -> float:
    """Share of letters that are Georgian (0..1). Used to detect broken extraction."""
    letters = len(LETTER.findall(text))
    return len(GEORGIAN.findall(text)) / letters if letters else 0.0


def is_mostly_latin(text: str, threshold: float = 0.6) -> bool:
    letters = len(LETTER.findall(text))
    return letters > 0 and len(LATIN.findall(text)) / letters >= threshold
