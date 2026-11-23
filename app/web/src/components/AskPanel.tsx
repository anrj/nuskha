import { createSignal } from "solid-js";
import { Button, Card, Spinner } from "./ui";

export function AskPanel(props: { asking: boolean; onAsk: (question: string) => void }) {
  const [draft, setDraft] = createSignal("");
  return (
    <Card>
      <form
        class="flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          const q = draft().trim();
          if (q.length >= 2) props.onAsk(q);
        }}
      >
        <input
          class="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-base outline-none focus:border-stone-900 focus:ring-2 focus:ring-stone-200"
          placeholder="მაგ.: ხელშეკრულების ვადა ან xelshekrulebis vada"
          value={draft()}
          onInput={(e) => setDraft(e.currentTarget.value)}
          maxlength="1000"
          aria-label="კითხვა"
        />
        <Button type="submit" disabled={props.asking || draft().trim().length < 2}>
          {props.asking ? <Spinner /> : null}
          ძებნა
        </Button>
      </form>
    </Card>
  );
}
