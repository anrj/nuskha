import { createMemo, For, Show } from "solid-js";
import { type Answer, type Citation, unitLabel } from "../api";
import { Badge, Button, Card, CardTitle } from "./ui";

const CITE = /(\[\d+\])/g;

export function AnswerView(props: { answer: Answer; onOpen: (c: Citation) => void }) {
  const parts = createMemo(() => props.answer.answer.split(CITE).filter(Boolean));
  const byN = createMemo(() => new Map(props.answer.citations.map((c) => [c.n, c])));

  return (
    <Card class="flex flex-col gap-4">
      <div>
        <CardTitle>პასუხი</CardTitle>
        <p class="whitespace-pre-line leading-relaxed">
          <For each={parts()} keyed={false}>
            {(part) => (
              <Show when={byN().get(Number(part().slice(1, -1)))} fallback={<>{part()}</>}>
                {(c) => (
                  <button
                    class="mx-0.5 rounded bg-stone-900 px-1.5 text-xs font-semibold text-white align-super hover:bg-stone-700"
                    onClick={() => props.onOpen(c())}
                    title={`${c().filename}, ${unitLabel(c().filename)} ${c().page}`}
                  >
                    {c().n}
                  </button>
                )}
              </Show>
            )}
          </For>
        </p>
        <Show when={props.answer.mode === "none" && props.answer.citations.length > 0}>
          <p class="mt-2 text-xs text-stone-500">AI პასუხი გამორთულია (LLM გასაღები არ არის) — ნაჩვენებია ყველაზე შესაბამისი ფრაგმენტი.</p>
        </Show>
        <Show when={props.answer.mode === "unavailable"}>
          <p class="mt-2 text-xs text-amber-700">AI დროებით გადატვირთულია — ნაჩვენებია ყველაზე შესაბამისი ფრაგმენტი. სცადე ცოტა ხანში.</p>
        </Show>
      </div>

      <Show when={props.answer.citations.length}>
        <div>
          <h3 class="mb-2 text-sm font-semibold text-stone-700">წყაროები</h3>
          <ol class="flex flex-col gap-2">
            <For each={props.answer.citations} keyed={(c) => c.chunk_id}>
              {(c) => (
                <li class="rounded-xl bg-stone-50 p-3 ring-1 ring-stone-200">
                  <div class="mb-1 flex items-center justify-between gap-2">
                    <span class="flex min-w-0 items-center gap-2 text-sm font-medium">
                      <Badge>{c().n}</Badge>
                      <span class="truncate">{c().filename}</span>
                      <span class="shrink-0 text-stone-500">· {unitLabel(c().filename)} {c().page}</span>
                    </span>
                    <Button variant="secondary" class="shrink-0 px-3 py-1" onClick={() => props.onOpen(c())}>
                      გახსნა
                    </Button>
                  </div>
                  <p class="text-sm leading-relaxed text-stone-600">{c().snippet}</p>
                </li>
              )}
            </For>
          </ol>
        </div>
      </Show>
    </Card>
  );
}
