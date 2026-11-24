import { createSignal, For, Show } from "solid-js";
import { type Doc, unitLabel } from "../api";
import { Badge, Card, CardTitle } from "./ui";

const statusLabel = { ready: "მზადაა", processing: "მუშავდება", failed: "შეცდომა" } as const;
const statusTone = { ready: "success", processing: "info", failed: "danger" } as const;

export function DocumentList(props: { docs: Doc[]; onDelete: (doc: Doc) => Promise<void> }) {
  const [deleting, setDeleting] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);

  async function remove(doc: Doc) {
    if (!window.confirm(`წავშალო „${doc.filename}“? ფაილი და მისი ინდექსი სამუდამოდ წაიშლება.`)) return;
    setDeleting(doc.id);
    setError(null);
    try {
      await props.onDelete(doc);
    } catch (e) {
      setError(`${doc.filename}: ${(e as Error).message}`);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <Card>
      <CardTitle>ჩემი დოკუმენტები</CardTitle>
      <ul class="divide-y divide-stone-100">
        <For each={props.docs} keyed={(d) => d.id} fallback={<li class="py-2 text-sm text-stone-500">ჯერ არცერთი დოკუმენტი არ ატვირთულა.</li>}>
          {(doc) => (
            <li class="flex flex-col gap-1 py-2.5">
              <div class="flex items-center justify-between gap-2">
                <span class="truncate text-sm font-medium" title={doc().filename}>{doc().filename}</span>
                <span class="flex shrink-0 items-center gap-2">
                  <Badge tone={statusTone[doc().status]}>{statusLabel[doc().status]}</Badge>
                  <button
                    class="rounded px-1.5 text-xs text-stone-400 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                    disabled={deleting() === doc().id}
                    onClick={() => remove(doc())}
                    title="წაშლა"
                    aria-label={`წაშლა: ${doc().filename}`}
                  >
                    წაშლა
                  </button>
                </span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <Show when={doc().page_count}>{(n) => <Badge>{n()} {unitLabel(doc().filename)}</Badge>}</Show>
                <Show when={doc().georgian_ratio !== null && doc().status === "ready"}>
                  <Badge>ქართული {Math.round((doc().georgian_ratio ?? 0) * 100)}%</Badge>
                </Show>
                <Show when={doc().legacy_font_fixed}>
                  <Badge tone="warning">ძველი შრიფტი → Unicode</Badge>
                </Show>
              </div>
              <Show when={doc().error}>{(err) => <p class="text-xs text-red-600">{err()}</p>}</Show>
            </li>
          )}
        </For>
      </ul>
      <Show when={error()}>{(msg) => <p class="mt-2 text-sm text-red-600">{msg()}</p>}</Show>
    </Card>
  );
}
