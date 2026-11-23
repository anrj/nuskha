"""Pre-Unicode Georgian text ("AcadNusx-style"): Georgian typed as Latin letters on the Georgian keyboard layout.

On screen it renders as "ხელშეკრულება"; in the file it is "xelSekruleba". Detection looks only at the text,
never at font names: a Latin line is converted when the converted result reads as Georgian and the original
does not read as English or informal translit ("xelshekruleba").
"""
import re

KEYBOARD = {
    "a": "ა", "b": "ბ", "g": "გ", "d": "დ", "e": "ე", "v": "ვ", "z": "ზ", "T": "თ",
    "i": "ი", "k": "კ", "l": "ლ", "m": "მ", "n": "ნ", "o": "ო", "p": "პ", "J": "ჟ",
    "r": "რ", "s": "ს", "t": "ტ", "u": "უ", "f": "ფ", "q": "ქ", "R": "ღ", "y": "ყ",
    "S": "შ", "C": "ჩ", "c": "ც", "Z": "ძ", "w": "წ", "W": "ჭ", "x": "ხ", "j": "ჯ", "h": "ჰ",
}
_TABLE = str.maketrans(KEYBOARD)
_LEGACY_UPPER = frozenset("TJRSCZW")  # the only capitals the layout uses

# High-frequency Georgian words and endings, checked on the CONVERTED token.
_GEORGIAN_WORDS = frozenset(
    "და რომ არ არის ეს თუ მისი მიერ შესახებ წლის ლარი ლარს უნდა იყოს როგორც ასევე ყველა შემდეგ ხოლო მაგრამ "
    "ამ ერთი ქ შპს თვის დღე დღით წელს თანახმად საფუძველი ბრძანება ხელშეკრულება მიეცეს შესაბამისად არც "
    "ჩვენ თქვენ იგი ისინი ვერ კი უკვე მხოლოდ ყოველი სადაც როდესაც თუმცა".split()
)
_GEORGIAN_ENDINGS = ("ის", "ში", "ზე", "ით", "ად", "ება", "ობა", "ების", "ებს", "ები", "ული", "ელი", "ალი",
                     "მდე", "დან", "თვის", "ისა", "ი")
# Signs the Latin text is English or informal translit rather than keyboard-layout Georgian.
# Words that are also common Georgian on this layout (or = ორ, da = და, ar = არ) are deliberately left out.
_ENGLISH_WORDS = frozenset(
    "the and of to in for with on at by this that be are from as it we you not have will your our all can has "
    "was were which their they there been per shall may must".split()
)
_ENGLISH_PATTERN = re.compile(r"th|wh|ing$|tion$", re.I)
_TRANSLIT = re.compile(r"sh|ch|zh|gh|kh", re.I)  # informal translit digraphs; keyboard layout uses capitals instead

_TOKEN = re.compile(r"[A-Za-z]+")
_PROTECTED = re.compile(r"\S+@\S+|https?://\S+|www\.\S+")  # emails and URLs are never converted


def from_legacy_font(text: str) -> str:
    """Convert keyboard-layout Georgian to Unicode (no detection)."""
    return text.translate(_TABLE)


fix_keyboard_layout = from_legacy_font  # same mapping; used for queries typed on the wrong layout


def _convertible(token: str) -> bool:
    return all(c.islower() or c in _LEGACY_UPPER for c in token)


def _score(line: str) -> tuple[int, int, int, bool, bool]:
    """(convertible tokens, Georgian-looking, English-looking, strong signal, translit veto)."""
    tokens = [t for t in _TOKEN.findall(_PROTECTED.sub(" ", line)) if len(t) >= 2]
    n = ka = en = 0
    strong = mixed_seen = translit = False
    for t in tokens:
        if _TRANSLIT.search(t):
            translit = True
            continue
        if t.lower() in _ENGLISH_WORDS or _ENGLISH_PATTERN.search(t):
            en += 1
            continue
        if not _convertible(t):
            continue
        n += 1
        ka_token = from_legacy_font(t)
        mixed = bool(re.search(r"[a-z][TJRSCZW]", t))  # "xelSekruleba", "saqarTvelo": capitals mid-word
        mixed_seen |= mixed
        if mixed or ka_token in _GEORGIAN_WORDS:
            ka += 1
            strong = True
        elif len(ka_token) >= 4 and ka_token.endswith(_GEORGIAN_ENDINGS):
            ka += 1
    return n, ka, en, strong, translit and not mixed_seen


def _convert_line(line: str) -> str:
    parts, last = [], 0
    for m in _PROTECTED.finditer(line):
        parts.append(_TOKEN.sub(lambda t: from_legacy_font(t.group()) if _convertible(t.group()) else t.group(),
                                line[last:m.start()]))
        parts.append(m.group())
        last = m.end()
    parts.append(_TOKEN.sub(lambda t: from_legacy_font(t.group()) if _convertible(t.group()) else t.group(), line[last:]))
    return "".join(parts)


def fix_legacy_text(texts: list[str]) -> tuple[list[str], bool]:
    """Convert the legacy lines of a document. Takes all pages at once so the decision for short lines
    (an Excel cell, a title) can lean on the rest of the document."""
    lines = [t.split("\n") for t in texts]
    scores = [[_score(line) for line in page] for page in lines]

    def is_legacy(n: int, ka: int, en: int, strong: bool, translit: bool) -> bool:
        if n == 0 or translit or en > 0.25 * (n + en):
            return False
        return ka / n >= 0.3 if n >= 3 else strong

    flat = [s for page in scores for s in page if s[0] >= 3]
    doc_is_legacy = bool(flat) and sum(is_legacy(*s) for s in flat) / len(flat) >= 0.6

    out, changed = [], False
    for page_lines, page_scores in zip(lines, scores):
        new = []
        for line, score in zip(page_lines, page_scores):
            n, _, en, _, translit = score
            convert = is_legacy(*score) or (doc_is_legacy and n > 0 and en == 0 and not translit)
            new.append(_convert_line(line) if convert else line)
            changed |= convert
        out.append("\n".join(new))
    return out, changed
