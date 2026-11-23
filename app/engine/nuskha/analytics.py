"""Server-side PostHog events. Call only after the related DB write has committed."""
from posthog import Posthog

from .config import EVENTS, settings

_client = Posthog(settings.posthog_key, host=settings.posthog_host) if settings.posthog_key else None


def capture(distinct_id: str, event_key: str, properties: dict) -> None:
    if _client is None:
        return
    _client.capture(EVENTS[event_key], distinct_id=distinct_id,
                    properties={**properties, "environment": settings.environment, "source": "server"})
    _client.flush()  # safe on serverless hosts; cheap at demo volume
