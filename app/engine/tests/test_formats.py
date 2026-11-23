"""Every supported format parses to Georgian text with the right citation unit (page/slide/sheet)."""
import io
import zipfile
from pathlib import Path

import pytest

from nuskha.ingest.parse import parse
from make_samples import to_acadnusx


def test_csv_rows_carry_column_names(samples):
    p = parse("employees.csv", (samples / "employees.csv").read_bytes())
    text = p.pages[0].text
    assert "სახელი: ნინო ბერიძე; თანამდებობა: ბუღალტერი" in text
    assert "ხელფასი (ლარი): 3200" in text and p.georgian_ratio > 0.8


def test_semicolon_csv_and_tsv():
    data = "სახელი;ქალაქი\nნინო;ქუთაისი\n".encode()
    assert parse("a.csv", data).pages[0].text == "სახელი: ნინო; ქალაქი: ქუთაისი"
    assert parse("a.tsv", "სახელი\tქალაქი\nნინო\tთბილისი\n".encode()).pages[0].text == "სახელი: ნინო; ქალაქი: თბილისი"


def test_xlsx_sheets_are_pages_and_legacy_cells_fixed(samples):
    p = parse("vacations.xlsx", (samples / "vacations.xlsx").read_bytes())
    assert [pg.number for pg in p.pages] == [1, 2]
    assert "თანამშრომელი: გიორგი კაპანაძე; დაწყება: 2026-12-01" in p.pages[0].text
    assert "ნინო ბერიძე" in p.pages[1].text and p.legacy_font_fixed


def test_pptx_slides_are_pages():
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    for title, body, font in [("წლიური ანგარიში", "შემოსავალი გაიზარდა 12%-ით", None),
                              ("გეგმა 2027", to_acadnusx("ახალი ოფისი ბათუმში"), "AcadNusx")]:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = title
        run = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1)).text_frame.paragraphs[0].add_run()
        run.text = body
        if font:
            run.font.name = font
    buf = io.BytesIO()
    prs.save(buf)
    p = parse("deck.pptx", buf.getvalue())
    assert [pg.number for pg in p.pages] == [1, 2]
    assert "12%-ით" in p.pages[0].text and "ახალი ოფისი ბათუმში" in p.pages[1].text and p.legacy_font_fixed


def _odt(paragraphs: list[str], font: str) -> bytes:
    body = "".join(f"<text:p>{t}</text:p>" for t in paragraphs)
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.3">'
        f'<office:font-face-decls><style:font-face style:name="{font}"/></office:font-face-decls>'
        f"<office:body><office:text>{body}</office:text></office:body></office:document-content>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        z.writestr("content.xml", content)
    return buf.getvalue()


@pytest.mark.parametrize("font,legacy", [("Arial", False), ("AcadNusx", True)])
def test_odt_google_docs_export(font, legacy):
    paras = ["შიდა განაწესი", "სამუშაო დღე იწყება 09:00 საათზე."]
    data = _odt([to_acadnusx(t) for t in paras] if legacy else paras, font)
    p = parse("policy.odt", data)
    assert "სამუშაო დღე იწყება 09:00 საათზე." in p.pages[0].text and p.legacy_font_fixed is legacy


def test_rtf_unicode_georgian():
    text = "ხელშეკრულება"
    rtf = "{\\rtf1\\ansi{\\fonttbl\\f0 Sylfaen;}\\f0 " + "".join(f"\\u{ord(c)}?" for c in text) + "}"
    assert parse("memo.rtf", rtf.encode()).pages[0].text == text


def test_html_skips_scripts_and_keeps_blocks():
    html = "<html><style>p{}</style><body><h1>ინსტრუქცია</h1><p>დაურეკეთ IT-ს.</p><script>x()</script></body></html>"
    text = parse("page.html", html.encode()).pages[0].text
    assert text == "ინსტრუქცია\n\nდაურეკეთ IT-ს." 


LEGACY = Path(__file__).parent / "fixtures" / "legacy"  # made by LibreOffice from Georgian .docx/.xlsx/.pptx


@pytest.fixture
def no_libreoffice(monkeypatch):
    """Exercise the pure-Python readers (what free hosting has), even where soffice is installed."""
    import nuskha.ingest.parse as parse_mod

    monkeypatch.setattr(parse_mod.shutil, "which", lambda name: None)


def test_doc_word97_unicode_with_table(no_libreoffice):
    p = parse("contract.doc", (LEGACY / "unicode.doc").read_bytes())
    text = p.pages[0].text
    assert "დასაქმებულის ხელფასი შეადგენს 1800 ლარს თვეში." in text
    assert "ლევანი | ზუგდიდი" in text and not p.legacy_font_fixed


def test_doc_word97_acadnusx(no_libreoffice):
    p = parse("order.doc", (LEGACY / "acad.doc").read_bytes())
    assert p.pages[0].text == "ბრძანება №7\n\nეკა ჩხეიძეს მიეცეს შვებულება 3 დღით." and p.legacy_font_fixed


def test_xls_excel97_sheets_numbers_and_legacy_cells(no_libreoffice):
    p = parse("salaries.xls", (LEGACY / "book.xls").read_bytes())
    assert [pg.number for pg in p.pages] == [1, 2]
    assert "სახელი: ლევანი; ხელფასი: 1800; თარიღი: 2026-05-01" in p.pages[0].text
    assert "ხელფასი: 2100.5" in p.pages[0].text
    assert "თანამშრომელი: ეკა ჩხეიძე; დღეები: 3" in p.pages[1].text and p.legacy_font_fixed


def test_ppt_powerpoint97_one_page_per_slide(no_libreoffice):
    p = parse("report.ppt", (LEGACY / "deck.ppt").read_bytes())
    assert [pg.number for pg in p.pages] == [1, 2]
    assert "შემოსავალი გაიზარდა 12%-ით" in p.pages[0].text and "ახალი ოფისი ბათუმში" in p.pages[1].text


def test_fake_xls_from_accounting_software_is_read_as_html_or_csv(no_libreoffice):
    html = "<html><body><table><tr><th>ანგარიში</th><th>თანხა</th></tr><tr><td>ხელფასი</td><td>2500</td></tr></table></body></html>"
    assert "ანგარიში" in parse("export.xls", html.encode()).pages[0].text
    assert parse("export.xls", "ანგარიში;თანხა\nხელფასი;2500\n".encode()).pages[0].text == "ანგარიში: ხელფასი; თანხა: 2500"


def test_rtf_saved_as_doc(no_libreoffice):
    rtf = "{\\rtf1\\ansi " + "".join(f"\\u{ord(c)}?" for c in "ბრძანება") + "}"
    assert parse("order.doc", rtf.encode()).pages[0].text == "ბრძანება"


def test_broken_doc_explains_what_to_do(no_libreoffice):
    with pytest.raises(ValueError, match="Save it as .docx"):
        parse("broken.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600)
