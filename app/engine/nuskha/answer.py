"""Turn retrieved chunks into an answer with numbered citations [n]."""
import re

from .config import settings
from .providers import ProviderError, post_json
from .georgian import georgian_ratio, normalize, query_variants
from .search import Hit

_SYSTEM = """You answer questions about the user's own documents (often Georgian office/HR files: contracts, invoices, orders).
Rules:
- Use ONLY the numbered sources provided. If they don't contain the answer, say so plainly.
- Answer in the language of the question. If the question is Latin-typed Georgian, answer in Georgian.
- Cite every claim with its source number in square brackets, e.g. [1] or [2][3].
- Be concise: a direct answer first, then key details (dates, amounts, names) exactly as written in the source."""

_CITE = re.compile(r"\[(\d+)\]")


def _stems(query: str) -> set[str]:
    """Query term prefixes that survive Georgian suffixes: ხელშეკრულების -> ხელშეკრულ."""
    terms = {t for v in query_variants(query) for t in normalize(v).split() if len(t) >= 4}
    return {t[: max(4, len(t) - 3)] for t in terms}


def _snippet(text: str, query: str, width: int = 320) -> str:
    """The window of `text` containing the most distinct query terms."""
    low = text.lower()  # length-preserving, so offsets map back to `text`
    stems = _stems(query)
    hits = sorted((m.start(), stem) for stem in stems for m in re.finditer(re.escape(stem), low))
    if not hits or len(text) <= width:
        return text[:width].strip() + ("…" if len(text) > width else "")
    best_start, best_score = 0, -1
    for pos, _ in hits:
        start = max(0, pos - width // 4)
        score = len({stem for p, stem in hits if start <= p < start + width - 10})
        if score > best_score:
            best_start, best_score = start, score
    if best_start:  # don't cut a word in half
        space = text.find(" ", best_start)
        best_start = space + 1 if 0 <= space < best_start + 20 else best_start
    end = best_start + width
    return ("…" if best_start else "") + text[best_start:end].strip() + ("…" if end < len(text) else "")


def _citation(n: int, hit: Hit, question: str) -> dict:
    return {
        "n": n, "chunk_id": hit.chunk_id, "document_id": hit.document_id,
        "filename": hit.filename, "page": hit.page, "snippet": _snippet(hit.text, question),
    }


def answer(question: str, hits: list[Hit]) -> tuple[str, list[dict], str]:
    """Returns (answer_text, citations, mode)."""
    georgian = georgian_ratio(question) > 0.5 or len(query_variants(question)) > 1
    if not hits:
        msg = "თქვენს დოკუმენტებში შესაბამისი ინფორმაცია ვერ მოიძებნა." if georgian else "Nothing relevant was found in your documents."
        return msg, [], "none"

    if settings.answers == "none":
        return _best_passage(question, hits, georgian, "none")

    sources = "\n\n".join(f"[{i}] ({h.filename}, page {h.page})\n{h.text}" for i, h in enumerate(hits, 1))
    prompt = f"Sources:\n\n{sources}\n\nQuestion: {question}"
    try:
        text = _ask_llm(prompt)
    except ProviderError as e:  # every model busy or failing: still give the user their source
        print(f"AI provider error, showing best passage instead: {e}", flush=True)
        return _best_passage(question, hits, georgian, "unavailable")
    used = sorted({int(n) for n in _CITE.findall(text) if 1 <= int(n) <= len(hits)})
    return text, [_citation(n, hits[n - 1], question) for n in used], "llm"


def _best_passage(question: str, hits: list[Hit], georgian: bool, mode: str) -> tuple[str, list[dict], str]:
    top = hits[:3]
    head = "ყველაზე შესაბამისი ფრაგმენტი" if georgian else "Best matching passage"
    return f"{head} [1]:\n{_snippet(top[0].text, question, 260)}", [_citation(i, h, question) for i, h in enumerate(top, 1)], mode


def _ask_llm(prompt: str) -> str:
    """Gemini, Groq, OpenRouter, Mistral, Cerebras... all accept the OpenAI chat format.
    Tries the main model, then each fallback model; raises the last error if all fail."""
    error: ProviderError | None = None
    for model in [settings.llm_model, *settings.llm_fallback_models]:
        try:
            body = post_json(f"Answer ({model})", f"{settings.llm_base_url}/chat/completions", settings.llm_api_key, {
                "model": model, "max_tokens": 800, "temperature": 0.2,
                "messages": [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            }, retries=1)  # one quick retry per model; the fallback models are the real safety net
            return (body["choices"][0]["message"]["content"] or "").strip()
        except ProviderError as e:
            print(f"{e} — trying next model", flush=True)
            error = e
    raise error
