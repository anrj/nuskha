import { For, Show } from "solid-js";
import { type Doc, unitLabel } from "../api";
import { Badge, Card, CardTitle } from "./ui";

const statusLabel = { ready: "მზადაა", processing: "მუშავდება", failed: "შეცდომა" } as const;
const statusTone = { ready: "success", processing: "info", failed: "danger" } as const;

export function DocumentList(props: { docs: Doc[] }) {
  return (
    <Card>
      <CardTitle>ჩემი დოკუმენტები</CardTitle>
      <ul class="divide-y divide-stone-100">
        <For each={props.docs} keyed={(d) => d.id} fallback={<li class="py-2 text-sm text-stone-500">ჯერ არცერთი დოკუმენტი არ ატვირთულა.</li>}>
          {(doc) => (
            <li class="flex flex-col gap-1 py-2.5">
              <div class="flex items-center justify-between gap-2">
                <span class="truncate text-sm font-medium" title={doc().filename}>{doc().filename}</span>
                <Badge tone={statusTone[doc().status]}>{statusLabel[doc().status]}</Badge>
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
    </Card>
  );
}
