"""HTTP calls to AI providers, with errors that say what actually went wrong."""
import time

import httpx

_RETRYABLE = {429, 500, 502, 503, 504}  # rate limits and "model overloaded" are usually gone within seconds


class ProviderError(RuntimeError):
    """An AI provider rejected or failed a request. The message is safe to show to the user."""


def post_json(what: str, url: str, api_key: str, payload: dict, timeout: float = 90, retries: int = 2) -> dict:
    for attempt in range(retries + 1):
        try:
            r = httpx.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload, timeout=timeout)
        except httpx.HTTPError as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise ProviderError(f"{what}: could not reach {httpx.URL(url).host} ({type(e).__name__})") from e
        if r.status_code in _RETRYABLE and attempt < retries:
            time.sleep(1.5 * (attempt + 1))
            continue
        break
    if r.status_code >= 400:
        try:
            body = r.json()
            err = body[0] if isinstance(body, list) and body else body
            detail = (err.get("error") or {}).get("message") if isinstance(err, dict) else None
        except ValueError:
            detail = None
        raise ProviderError(f"{what} failed ({r.status_code}): {detail or r.text[:300]}")
    return r.json()
