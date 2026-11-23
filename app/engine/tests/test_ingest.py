from nuskha.georgian import normalize
from nuskha.ingest.chunk import chunk_pages
from nuskha.ingest.parse import Page, parse


def test_pdf_pages_and_georgian(samples):
    parsed = parse("contract.pdf", (samples / "contract.pdf").read_bytes())
    assert len(parsed.pages) == 2
    assert "2500 ლარს" in parsed.pages[0].text
    assert "კონფიდენციალურობა" in parsed.pages[1].text
    assert parsed.georgian_ratio > 0.9 and not parsed.legacy_font_fixed


def test_legacy_acadnusx_docx_is_converted(samples):
    parsed = parse("order.docx", (samples / "order.docx").read_bytes())
    assert parsed.legacy_font_fixed
    assert "გიორგი კაპანაძეს" in parsed.pages[0].text
    assert parsed.georgian_ratio > 0.9


def test_chunks_keep_pages_and_size():
    pages = [Page(1, "პირველი წინადადება. " * 80), Page(2, "მეორე გვერდი.")]
    chunks = chunk_pages(pages, size=300, overlap=50)
    assert all(len(c.text) <= 300 for c in chunks)
    assert {c.page for c in chunks} == {1, 2}
    assert chunks[-1].text == "მეორე გვერდი."


def test_invoice_amounts_survive_normalization(samples):
    text = normalize(parse("invoice.pdf", (samples / "invoice.pdf").read_bytes()).pages[0].text)
    assert "991.20 ლარი" in text and "ს/კ 205000412" in text
