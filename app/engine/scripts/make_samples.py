"""Generate realistic Georgian demo documents into ../samples (or a given folder).

  uv run python scripts/make_samples.py [out_dir]

- contract.pdf  (2 pages, Unicode Georgian)
- invoice.pdf   (Unicode Georgian, amounts and TIN)
- order.docx    (typed in the legacy AcadNusx font: tests the legacy-font fix)
- employees.csv (HR table: one row per employee)
- vacations.xlsx (2 sheets; the second is typed in AcadNusx)
All names and numbers are fictional.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # run as a plain script

import docx
import pymupdf

from nuskha.georgian.legacy import KEYBOARD

CONTRACT = [
    """შრომითი ხელშეკრულება №17

ქ. ქუთაისი, 2026 წლის 10 იანვარი

დამსაქმებელი: შპს „ნუსხა", საიდენტიფიკაციო კოდი 404000017.
დასაქმებული: ნინო ბერიძე.

1. ხელშეკრულების საგანი. დასაქმებული ინიშნება ბუღალტრის თანამდებობაზე.

2. ხელშეკრულების ვადა. ხელშეკრულება ძალაშია 2026 წლის 15 იანვრიდან 2027 წლის 14 იანვრამდე.

3. გამოსაცდელი ვადა შეადგენს 3 თვეს.

4. შრომის ანაზღაურება. თანამდებობრივი სარგო შეადგენს 2500 ლარს თვეში (დარიცხული), რომელიც ირიცხება ყოველი თვის 5 რიცხვამდე.

5. სამუშაო დრო: ორშაბათიდან პარასკევის ჩათვლით, 09:00-დან 18:00-მდე, ერთსაათიანი შესვენებით.""",
    """6. ანაზღაურებადი შვებულება შეადგენს წელიწადში 24 სამუშაო დღეს.

7. ხელშეკრულების შეწყვეტა. მხარეს შეუძლია ხელშეკრულების შეწყვეტა მეორე მხარისთვის 30 კალენდარული დღით ადრე წერილობითი შეტყობინებით.

8. კონფიდენციალურობა. დასაქმებული ვალდებულია არ გაამჟღავნოს კომპანიის კომერციული საიდუმლოება ხელშეკრულების შეწყვეტიდან 2 წლის განმავლობაში.

დამსაქმებლის სახელით: დავით მაისურაძე, დირექტორი
დასაქმებული: ნინო ბერიძე""",
]

INVOICE = """ანგარიშ-ფაქტურა №INV-2026-0412

თარიღი: 2026 წლის 3 ოქტომბერი
მომწოდებელი: შპს „ქართული ქაღალდი", ს/კ 205000412
მყიდველი: შპს „ნუსხა", ს/კ 404000017

1. ოფისის ქაღალდი A4 — 40 შეკვრა × 12.50 ლარი = 500.00 ლარი
2. პრინტერის კარტრიჯი — 4 ცალი × 85.00 ლარი = 340.00 ლარი

ჯამი დღგ-ის გარეშე: 840.00 ლარი
დღგ (18%): 151.20 ლარი
სულ გადასახდელი: 991.20 ლარი

გადახდის ვადა: 2026 წლის 20 ოქტომბერი.
საბანკო რეკვიზიტები: მიმღების ანგარიში მითითებულია ხელშეკრულებაში."""

ORDER = [
    "ბრძანება №45",
    "ანაზღაურებადი შვებულების მიცემის შესახებ",
    "ქ. ქუთაისი, 2026 წლის 20 ნოემბერი",
    "გიორგი კაპანაძეს, სისტემური ადმინისტრატორის თანამდებობაზე მომუშავეს, მიეცეს ანაზღაურებადი შვებულება 2026 წლის 1 დეკემბრიდან 5 დეკემბრის ჩათვლით, სულ 5 სამუშაო დღე.",
    "საფუძველი: გიორგი კაპანაძის 2026 წლის 18 ნოემბრის განცხადება.",
    "ბრძანება ძალაშია ხელმოწერისთანავე.",
    "დირექტორი: დავით მაისურაძე",
]

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/sylfaen.ttf",
]


def georgian_font() -> str:
    for f in _FONT_CANDIDATES:
        if Path(f).exists():
            return f
    raise FileNotFoundError("No font with Georgian glyphs found; add one to _FONT_CANDIDATES")


def write_pdf(path: Path, pages: list[str]) -> None:
    doc = pymupdf.open()
    font = georgian_font()
    for text in pages:
        page = doc.new_page()
        page.insert_font(fontname="geo", fontfile=font)
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), text, fontname="geo", fontsize=11)
    doc.save(path)


def to_acadnusx(text: str) -> str:
    reverse = {ka: lat for lat, ka in KEYBOARD.items()}
    return "".join(reverse.get(ch, ch) for ch in text)


def write_legacy_docx(path: Path, paragraphs: list[str]) -> None:
    d = docx.Document()
    for p in paragraphs:
        run = d.add_paragraph().add_run(to_acadnusx(p))
        run.font.name = "AcadNusx"
    d.save(path)


EMPLOYEES = [
    ["სახელი", "თანამდებობა", "დაწყების თარიღი", "ხელფასი (ლარი)", "ელფოსტა"],
    ["ნინო ბერიძე", "ბუღალტერი", "2026-01-15", "2500", "nino@nuskha.ge"],
    ["გიორგი კაპანაძე", "სისტემური ადმინისტრატორი", "2025-09-01", "3200", "giorgi@nuskha.ge"],
    ["თამარ ლომიძე", "HR მენეჯერი", "2024-03-10", "2800", "tamar@nuskha.ge"],
]

VACATIONS_2026 = [
    ["თანამშრომელი", "დაწყება", "დასრულება", "დღეები"],
    ["გიორგი კაპანაძე", "2026-12-01", "2026-12-05", 5],
    ["თამარ ლომიძე", "2026-08-10", "2026-08-21", 10],
]
SICK_LEAVE_LEGACY = [["თანამშრომელი", "ავადმყოფობის ფურცელი", "დღეები"], ["ნინო ბერიძე", "მარტი", 3]]


def write_csv(path: Path, rows: list[list]) -> None:
    import csv

    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel opens Georgian correctly
        csv.writer(f).writerows(rows)


def write_xlsx(path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "შვებულებები 2026"
    for r in VACATIONS_2026:
        ws.append(r)
    legacy = wb.create_sheet("ბიულეტენი")
    for r in SICK_LEAVE_LEGACY:
        legacy.append([to_acadnusx(v) if isinstance(v, str) else v for v in r])
    for row in legacy.iter_rows():
        for cell in row:
            cell.font = Font(name="AcadNusx")
    wb.save(path)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    write_pdf(out / "contract.pdf", CONTRACT)
    write_pdf(out / "invoice.pdf", [INVOICE])
    write_legacy_docx(out / "order.docx", ORDER)
    write_csv(out / "employees.csv", EMPLOYEES)
    write_xlsx(out / "vacations.xlsx")
    print(f"Wrote samples to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "samples")
