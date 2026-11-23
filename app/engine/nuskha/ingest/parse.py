"""Extract text from common office formats, page by page.

"Page" is the citation unit: a PDF page, a PowerPoint slide, an Excel sheet; everything else is page 1.
After extraction, every format goes through the same content-based check for pre-Unicode Georgian text
(see georgian/legacy.py). Google Docs / Sheets / Slides: users export them (File → Download).
"""
import csv
import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import docx
import pymupdf

from ..georgian import fix_legacy_text, georgian_ratio
from . import legacy_office


@dataclass
class Page:
    number: int
    text: str


@dataclass
class Parsed:
    pages: list[Page]
    legacy_font_fixed: bool = False

    @property
    def georgian_ratio(self) -> float:
        return georgian_ratio(" ".join(p.text for p in self.pages))


def _decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _rows_to_text(rows: list[list[str]]) -> str:
    """Tables become one self-contained line per row: 'Column: value; Column: value'.

    That way every chunk carries its column names, so 'ნინოს ხელფასი' matches the right row.
    """
    rows = [[c.strip() for c in r] for r in rows if any(c and c.strip() for c in r)]
    if not rows:
        return ""
    header, body = rows[0], rows[1:]
    if not body:
        return " | ".join(header)
    lines = []
    for r in body:
        cells = [f"{header[i] if i < len(header) and header[i] else f'col{i + 1}'}: {v}" for i, v in enumerate(r) if v]
        lines.append("; ".join(cells))
    return "\n\n".join(lines)


def _single(text: str) -> Parsed:
    return Parsed([Page(1, text)])


# ---------- formats ----------

def _pdf(data: bytes) -> Parsed:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return Parsed([Page(i, page.get_text("text").strip()) for i, page in enumerate(doc, start=1)])


def _docx(data: bytes) -> Parsed:
    d = docx.Document(io.BytesIO(data))
    paras = [p.text for p in d.paragraphs]
    for table in d.tables:
        paras.append(_rows_to_text([[cell.text for cell in row.cells] for row in table.rows]))
    return _single("\n\n".join(x for x in paras if x.strip()))


def _odt(data: bytes) -> Parsed:
    """OpenDocument text (LibreOffice, and Google Docs' 'Download as .odt')."""
    text_ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        content = ElementTree.fromstring(z.read("content.xml"))
    blocks = ["".join(el.itertext()) for el in content.iter() if el.tag in (f"{{{text_ns}}}p", f"{{{text_ns}}}h")]
    return _single("\n\n".join(b for b in blocks if b.strip()))


def _rtf(data: bytes) -> Parsed:
    from striprtf.striprtf import rtf_to_text

    return _single(rtf_to_text(_decode(data), errors="ignore").strip())


def _csv(data: bytes, delimiter: str | None = None) -> Parsed:
    text = _decode(data)
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
    return _single(_rows_to_text(list(csv.reader(io.StringIO(text), delimiter=delimiter))))


def _sheets_to_pages(sheets: list[tuple[str, list[list[str]]]]) -> Parsed:
    return Parsed([Page(i, f"{name}\n\n{body}") for i, (name, rows) in enumerate(sheets, start=1)
                   if (body := _rows_to_text(rows))])


def _xlsx(data: bytes) -> Parsed:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)  # values, not formulas
    sheets = [(ws.title, [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)])
              for ws in wb.worksheets]
    wb.close()
    return _sheets_to_pages(sheets)


def _pptx(data: bytes) -> Parsed:
    from pptx import Presentation

    pages = []
    for i, slide in enumerate(Presentation(io.BytesIO(data)).slides, start=1):
        lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                lines.append(shape.text_frame.text)
            if getattr(shape, "has_table", False) and shape.has_table:
                lines.append(_rows_to_text([[c.text_frame.text for c in r.cells] for r in shape.table.rows]))
        if slide.has_notes_slide:
            lines.append(slide.notes_slide.notes_text_frame.text)
        text = "\n\n".join(x for x in lines if x.strip())
        if text:
            pages.append(Page(i, text))
    return Parsed(pages)


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _html(data: bytes) -> Parsed:
    p = _HTMLText()
    p.feed(_decode(data))
    return _single(re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", "".join(p.parts))).strip())


def _xls(data: bytes) -> Parsed:
    return _sheets_to_pages(legacy_office.xls_sheets(data))


def _doc(data: bytes) -> Parsed:
    return _single(legacy_office.doc_text(data))


def _ppt(data: bytes) -> Parsed:
    return Parsed([Page(i, t) for i, t in enumerate(legacy_office.ppt_slides(data), start=1) if t.strip()])


_PARSERS = {
    ".pdf": _pdf, ".docx": _docx, ".odt": _odt, ".rtf": _rtf, ".csv": _csv, ".tsv": lambda d: _csv(d, "\t"),
    ".xlsx": _xlsx, ".pptx": _pptx, ".html": _html, ".htm": _html,
    ".txt": lambda d: _single(_decode(d)), ".md": lambda d: _single(_decode(d)),
    ".xls": _xls, ".doc": _doc, ".ppt": _ppt,
}
SUPPORTED = tuple(_PARSERS)
_MODERN = {".doc": ".docx", ".xls": ".xlsx", ".ppt": ".pptx"}
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _via_libreoffice(ext: str, data: bytes) -> Parsed | None:
    """Convert an old Office file to its modern format with LibreOffice, if it's installed."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    target = _MODERN[ext].lstrip(".")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{ext}"
        src.write_bytes(data)
        subprocess.run([soffice, "--headless", "--convert-to", target, "--outdir", tmp, str(src)],
                       capture_output=True, timeout=120, check=False)
        out = Path(tmp) / f"input.{target}"
        return _PARSERS[f".{target}"](out.read_bytes()) if out.exists() else None


def _sniff(ext: str, data: bytes) -> str | None:
    """What a '.doc/.xls/.ppt' really is when it isn't a binary Office file. Exports from accounting and
    bank software are often HTML or CSV named .xls, and many '.doc' files are really RTF."""
    head = data[:512].lstrip()
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"{\\rtf"):
        return ".rtf"
    if head[:1] == b"<" and re.search(rb"<(html|table|body|!doctype|\?xml)", head, re.I):
        return ".html"
    if data.startswith(b"PK"):
        return _MODERN[ext]
    return ".csv" if ext == ".xls" else None


def _extract(ext: str, data: bytes) -> Parsed:
    if ext not in _MODERN:
        return _PARSERS[ext](data)
    if not data.startswith(_OLE) and (real := _sniff(ext, data)):
        return _PARSERS[real](data)
    try:
        return _PARSERS[ext](data)
    except Exception as e:
        converted = _via_libreoffice(ext, data)
        if converted is not None:
            return converted
        raise ValueError(f"Couldn't read this {ext} file ({e}). Save it as {_MODERN[ext]} and upload again.") from e


def parse(filename: str, data: bytes) -> Parsed:
    ext = filename[filename.rfind("."):].lower() if "." in filename else ""
    if ext not in _PARSERS:
        raise ValueError(f"Unsupported file type: {ext or filename}. Supported: {', '.join(SUPPORTED)}")
    parsed = _extract(ext, data)
    texts, fixed = fix_legacy_text([p.text for p in parsed.pages])
    return Parsed([Page(p.number, t) for p, t in zip(parsed.pages, texts)], fixed)
