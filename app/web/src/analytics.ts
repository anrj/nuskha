// Browser-side PostHog. Person events fire only AFTER the server confirmed the action.
// posthog-js is loaded lazily, and only when a key is configured.
import type { PostHog } from "posthog-js";
import EVENTS from "../../events.json";
import { userId } from "./api";

type EventKey = Exclude<keyof typeof EVENTS, "_comment">;

const key = import.meta.env.VITE_POSTHOG_KEY;
let client: Promise<PostHog> | null = null;

export function initAnalytics() {
  if (!key) return;
  client = import("posthog-js").then(({ default: posthog }) => {
    posthog.init(key, {
      api_host: import.meta.env.VITE_POSTHOG_HOST ?? "https://eu.i.posthog.com",
      person_profiles: "identified_only",
    });
    posthog.identify(userId);
    // Lets the dashboard's internal-user filter drop local testing ("development").
    posthog.register({ environment: import.meta.env.MODE, source: "browser" });
    return posthog;
  });
}

export function track(event: EventKey, properties: Record<string, unknown>) {
  client?.then((posthog) => posthog.capture(EVENTS[event], properties));
}
