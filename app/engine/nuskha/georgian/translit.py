"""Informal Latin transliteration ("xelshekruleba", "qartuli") -> Georgian, for queries."""
import re

from .legacy import fix_keyboard_layout
from .normalize import is_mostly_latin

# Longest sequences first. Follows common informal usage: q=ქ, k=კ, t=თ, w=წ, x=ხ, y=ყ.
_MULTI = [
    ("ch'", "ჭ"), ("ts'", "წ"), ("tch", "ჭ"),
    ("sh", "შ"), ("ch", "ჩ"), ("zh", "ჟ"), ("dz", "ძ"), ("ts", "ც"), ("gh", "ღ"), ("kh", "ხ"),
    ("t'", "ტ"), ("k'", "კ"), ("p'", "პ"), ("q'", "ყ"),
]
_SINGLE = {
    "a": "ა", "b": "ბ", "g": "გ", "d": "დ", "e": "ე", "v": "ვ", "z": "ზ", "t": "თ", "i": "ი",
    "k": "კ", "l": "ლ", "m": "მ", "n": "ნ", "o": "ო", "p": "პ", "r": "რ", "s": "ს", "u": "უ",
    "f": "ფ", "q": "ქ", "x": "ხ", "j": "ჯ", "h": "ჰ", "y": "ყ", "w": "წ", "c": "ც",
}
_TOKEN = re.compile(r"[A-Za-z']+")
_MIXED_CASE = re.compile(r"[a-z][A-Z]|[A-Z]{1}[a-z]+[A-Z]")


def _translit_word(word: str) -> str:
    w, out, i = word.lower(), [], 0
    while i < len(w):
        for seq, ka in _MULTI:
            if w.startswith(seq, i):
                out.append(ka)
                i += len(seq)
                break
        else:
            out.append(_SINGLE.get(w[i], "" if w[i] == "'" else w[i]))
            i += 1
    return "".join(out)


def latin_to_georgian(text: str) -> str:
    return _TOKEN.sub(lambda m: _translit_word(m.group()), text)


def query_variants(query: str) -> list[str]:
    """The original query plus Georgian rewrites when it looks like Latin-typed Georgian.

    Searching all variants and fusing the rankings means a wrong guess costs little.
    """
    variants = [query]
    if is_mostly_latin(query):
        variants.append(latin_to_georgian(query))
        if _MIXED_CASE.search(query):  # "xelSekruleba": keyboard-layout style, case is meaningful
            variants.append(fix_keyboard_layout(query))
    return list(dict.fromkeys(variants))
