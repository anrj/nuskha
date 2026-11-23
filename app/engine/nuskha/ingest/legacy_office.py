"""Old binary Office formats (Word/Excel/PowerPoint 97–2003), still common in Georgian offices.

Pure Python, so it runs anywhere (free hosting included):
- .xls  via xlrd
- .doc  via the Word piece table (text only; fields and control marks cleaned up)
- .ppt  via the PowerPoint record stream (one page per slide)

When LibreOffice (`soffice`) is installed, files these readers can't handle are converted
to .docx/.xlsx/.pptx first and parsed with the modern readers instead (see parse.py).
"""
import io
import re
import struct
from datetime import datetime

import olefile

# ---------------- Excel 97–2003 ----------------

def xls_sheets(data: bytes) -> list[tuple[str, list[list[str]]]]:
    import xlrd

    book = xlrd.open_workbook(file_contents=data)
    sheets = []
    for sheet in book.sheets():
        rows = []
        for r in range(sheet.nrows):
            cells = []
            for c in range(sheet.ncols):
                cell = sheet.cell(r, c)
                if cell.ctype == xlrd.XL_CELL_TEXT:
                    value = cell.value
                elif cell.ctype == xlrd.XL_CELL_NUMBER:
                    value = str(int(cell.value)) if float(cell.value).is_integer() else str(cell.value)
                elif cell.ctype == xlrd.XL_CELL_DATE:
                    value = datetime(*xlrd.xldate_as_tuple(cell.value, book.datemode)).date().isoformat()
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = "TRUE" if cell.value else "FALSE"
                else:
                    value = ""
                cells.append(value)
            rows.append(cells)
        sheets.append((sheet.name, rows))
    return sheets


# ---------------- Word 97–2003 ----------------

_FIELD = re.compile(r"\x13[^\x13\x14\x15]*\x14?([^\x13\x15]*)\x15")  # keep a field's result, drop its code


def doc_text(data: bytes) -> str:
    ole = olefile.OleFileIO(io.BytesIO(data))
    word = ole.openstream("WordDocument").read()
    if struct.unpack_from("<H", word, 0)[0] != 0xA5EC:
        raise ValueError("Not a Word 97–2003 document")
    flags = struct.unpack_from("<H", word, 0x0A)[0]
    if flags & 0x0100:
        raise ValueError("Encrypted (password-protected) Word document")
    table = ole.openstream("1Table" if flags & 0x0200 else "0Table").read()
    fc_clx, lcb_clx = struct.unpack_from("<II", word, 0x01A2)
    clx = table[fc_clx:fc_clx + lcb_clx]

    i = 0
    while i < len(clx) and clx[i] == 0x01:  # skip Prc entries
        i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
    if i >= len(clx) or clx[i] != 0x02:
        raise ValueError("Unsupported Word layout (no piece table)")
    lcb = struct.unpack_from("<I", clx, i + 1)[0]
    plc = clx[i + 5:i + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
    parts = []
    for k in range(n):
        fc = struct.unpack_from("<I", plc, 4 * (n + 1) + 8 * k + 2)[0]
        length = cps[k + 1] - cps[k]
        if fc & 0x40000000:  # compressed: 8-bit cp1252 at fc/2
            start = (fc & 0x3FFFFFFF) // 2
            parts.append(word[start:start + length].decode("cp1252", errors="replace"))
        else:
            parts.append(word[fc:fc + 2 * length].decode("utf-16le", errors="replace"))
    text = "".join(parts)

    text = _FIELD.sub(r"\1", text)
    text = text.replace("\x07\x07", "\n").replace("\x07", " | ")  # end of row / end of cell
    text = re.sub(r"[\r\x0b\x0c]", "\n", text)                   # paragraph, line and page breaks
    text = re.sub(r"[\x00-\x08\x0e-\x1f]", "", text)              # objects, footnote marks, leftovers
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"\n", "\n\n", text)).strip()


# ---------------- PowerPoint 97–2003 ----------------

_CONTAINER_SLIDE, _CONTAINER_NOTES, _CONTAINER_MASTER = 0x03EE, 0x03F0, 0x03F8
_SLIDE_LIST, _SLIDE_PERSIST = 0x0FF0, 0x03F3
_TEXT_CHARS, _TEXT_BYTES = 0x0FA0, 0x0FA8


def ppt_slides(data: bytes) -> list[str]:
    ole = olefile.OleFileIO(io.BytesIO(data))
    stream = ole.openstream("PowerPoint Document").read()
    outline: list[list[str]] = []   # text from the slide list (titles/placeholders), in slide order
    drawn: list[list[str]] = []     # text from each slide's own drawing (free text boxes), in stream order

    def walk(start: int, end: int, ctx: tuple[int, ...]) -> None:
        pos = start
        while pos + 8 <= end:
            ver_inst, rtype, rlen = struct.unpack_from("<HHI", stream, pos)
            body_start, body_end = pos + 8, min(pos + 8 + rlen, end)
            if (ver_inst & 0x000F) == 0x000F:  # container
                if rtype == _CONTAINER_SLIDE:
                    drawn.append([])
                if rtype in (_CONTAINER_NOTES, _CONTAINER_MASTER):
                    pos = body_end
                    continue
                inst = ver_inst >> 4
                if rtype == _SLIDE_LIST and inst != 0:  # instance 0 = slides; 1 = masters, 2 = notes
                    pos = body_end
                    continue
                walk(body_start, body_end, ctx + (rtype,))
            elif rtype == _SLIDE_PERSIST and _SLIDE_LIST in ctx:
                outline.append([])
            elif rtype in (_TEXT_CHARS, _TEXT_BYTES):
                raw = stream[body_start:body_end]
                text = raw.decode("utf-16le" if rtype == _TEXT_CHARS else "latin-1", errors="replace")
                text = text.replace("\r", "\n").replace("\x0b", "\n").strip()
                if text:
                    if _SLIDE_LIST in ctx and outline:
                        outline[-1].append(text)
                    elif _CONTAINER_SLIDE in ctx and drawn:
                        drawn[-1].append(text)
            pos = body_end

    walk(0, len(stream), ())
    count = max(len(outline), len(drawn))
    slides = []
    for i in range(count):
        parts = (outline[i] if i < len(outline) else []) + [t for t in (drawn[i] if i < len(drawn) else [])
                                                              if t not in (outline[i] if i < len(outline) else [])]
        slides.append("\n\n".join(parts))
    return slides
