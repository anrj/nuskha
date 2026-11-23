from nuskha.georgian import (
    fix_legacy_text, from_legacy_font, georgian_ratio, latin_to_georgian, normalize, query_variants,
)


def test_normalize_folds_mtavruli_and_cleans():
    assert normalize("ᲮᲔᲚᲨᲔᲙᲠᲣᲚᲔᲑᲐ") == "ხელშეკრულება"
    assert normalize("ხელ​შეკრულება") == "ხელშეკრულება"
    assert normalize("ხელშეკრუ-\n ლება  „ტესტი“") == 'ხელშეკრულება "ტესტი"'


def test_georgian_ratio():
    assert georgian_ratio("ხელშეკრულება") == 1.0
    assert georgian_ratio("xelSekruleba") == 0.0
    assert georgian_ratio("123 !!") == 0.0


def test_legacy_font_conversion():
    assert from_legacy_font("xelSekruleba") == "ხელშეკრულება"
    assert from_legacy_font("Sromis xelSekruleba") == "შრომის ხელშეკრულება"
    assert from_legacy_font("saqarTvelo") == "საქართველო"


def _fix(*pages):
    return fix_legacy_text(list(pages))


def test_detects_legacy_text_by_content():
    text, fixed = _fix("Sromis xelSekruleba dadebulia 2026 wlis 10 ianvars.")
    assert fixed and text == ["შრომის ხელშეკრულება დადებულია 2026 წლის 10 იანვარს."]
    assert _fix("brZaneba №7") == (["ბრძანება №7"], True)          # short line, but capitals mid-word


def test_leaves_english_translit_and_codes_alone():
    for line in [
        "The employee shall receive a salary of 2500 GEL per month.",
        "Invoice payment is overdue, please contact accounting.",
        "xelshekrulebis vada aris ori weli",                      # informal translit, not keyboard layout
        "Send it to nino@nuskha.ge or see https://nuskha.ge/docs",
        "getUserName returns JSON from the API",
        "INV-2026-0412 A4 LTD",
    ]:
        assert _fix(line) == ([line], False), line


def test_mixed_document_converts_only_legacy_lines():
    english = "This contract is written in English and Georgian."
    legacy = "es xelSekruleba Sedgenilia or enaze."
    (out,), fixed = _fix(f"{english}\n{legacy}")
    assert fixed and out == f"{english}\nეს ხელშეკრულება შედგენილია ორ ენაზე."


def test_short_lines_follow_the_document():
    # A spreadsheet: header and long rows are clearly legacy, so the short name cell is converted too.
    rows = "TanamSromeli: eka CxeiZe; dReebi: 3\neka\nsaxelfaso uwyisi: TanamSromlis Sromis anazRaureba"
    (out,), fixed = _fix(rows)
    assert fixed and out.split("\n")[1] == "ეკა"
    assert _fix("eka") == (["eka"], False)                          # alone, too ambiguous to touch


def test_translit():
    assert latin_to_georgian("xelshekruleba") == "ხელშეკრულება"
    assert latin_to_georgian("qartuli") == "ქართული"
    assert latin_to_georgian("gamarjoba") == "გამარჯობა"
    assert latin_to_georgian("shvebuleba") == "შვებულება"


def test_query_variants():
    assert query_variants("ხელშეკრულება") == ["ხელშეკრულება"]
    v = query_variants("xelshekruleba vada")
    assert v[0] == "xelshekruleba vada" and "ხელშეკრულება ვადა" in v
    assert "ხელშეკრულება" in query_variants("xelSekruleba")


def test_snippet_centers_on_matched_terms():
    from nuskha.answer import _snippet

    text = "შესავალი. " * 40 + "2. ხელშეკრულების ვადა. ხელშეკრულება ძალაშია 2026 წლის 15 იანვრიდან. " + "დასასრული. " * 40
    snip = _snippet(text, "xelshekrulebis vada", width=160)
    assert "ხელშეკრულების ვადა" in snip and snip.startswith("…")
