"""Answer providers without network: the OpenAI-compatible call is faked."""
import dataclasses

import httpx

from nuskha import answer as answer_mod
from nuskha.search import Hit

HITS = [
    Hit(1, "d1", "contract.pdf", 1, "თანამდებობრივი სარგო შეადგენს 2500 ლარს თვეში.", 0.9),
    Hit(2, "d1", "contract.pdf", 2, "ანაზღაურებადი შვებულება შეადგენს 24 სამუშაო დღეს.", 0.5),
]


def test_llm_answer_parses_citations(monkeypatch):
    s = dataclasses.replace(
        answer_mod.settings, llm_base_url="https://example.test/v1", llm_api_key="k", llm_model="m",
    )
    monkeypatch.setattr(answer_mod, "settings", s)
    seen = {}

    def fake_post(url, headers, json, timeout):  # noqa: A002 (mirrors httpx.post)
        seen.update(url=url, model=json["model"], auth=headers["Authorization"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "ხელფასი 2500 ლარია [1]."}}]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    text, citations, mode = answer_mod.answer("რამდენია ხელფასი?", HITS)
    assert mode == "llm" and text.endswith("[1].")
    assert [c["n"] for c in citations] == [1] and citations[0]["page"] == 1
    assert seen == {"url": "https://example.test/v1/chat/completions", "model": "m", "auth": "Bearer k"}


def test_no_llm_returns_best_passage():
    text, citations, mode = answer_mod.answer("სარგო", HITS)
    assert mode == "none" and "[1]" in text and len(citations) == 2


def test_provider_errors_carry_the_provider_message(monkeypatch):
    import pytest

    from nuskha.providers import ProviderError, post_json

    def fake_post(url, headers, json, timeout):  # noqa: A002
        return httpx.Response(400, json={"error": {"message": "API key not valid"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(ProviderError, match=r"Embeddings failed \(400\): API key not valid"):
        post_json("Embeddings", "https://example.test/v1/embeddings", "k", {})


def test_busy_model_falls_back_then_degrades_to_best_passage(monkeypatch):
    s = dataclasses.replace(answer_mod.settings, llm_base_url="https://example.test/v1", llm_api_key="k",
                            llm_model="main", llm_fallback_models=["backup"])
    monkeypatch.setattr(answer_mod, "settings", s)
    import nuskha.providers as providers

    monkeypatch.setattr(providers.time, "sleep", lambda _: None)
    calls = []

    def busy_then_ok(url, headers, json, timeout):  # noqa: A002
        calls.append(json["model"])
        if json["model"] == "main":
            return httpx.Response(503, json={"error": {"message": "high demand"}}, request=httpx.Request("POST", url))
        return httpx.Response(200, json={"choices": [{"message": {"content": "პასუხი [2]"}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", busy_then_ok)
    text, citations, mode = answer_mod.answer("შვებულება", HITS)
    assert mode == "llm" and calls == ["main", "main", "backup"] and citations[0]["n"] == 2

    monkeypatch.setattr(httpx, "post", lambda url, headers, json, timeout: httpx.Response(
        503, json={"error": {"message": "high demand"}}, request=httpx.Request("POST", url)))
    text, citations, mode = answer_mod.answer("შვებულება", HITS)
    assert mode == "unavailable" and citations and "[1]" in text
