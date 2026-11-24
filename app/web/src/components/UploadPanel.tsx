import { createSignal, For, Show } from "solid-js";
import { api } from "../api";
import { Card, CardTitle, Spinner } from "./ui";

const ACCEPT = ".pdf,.docx,.doc,.odt,.rtf,.txt,.md,.html,.htm,.csv,.tsv,.xlsx,.xls,.pptx,.ppt";

export function UploadPanel(props: { onUploaded: () => void }) {
  const [busy, setBusy] = createSignal<string[]>([]);
  const [error, setError] = createSignal<string | null>(null);
  const [dragging, setDragging] = createSignal(false);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    for (const file of Array.from(files)) {
      setBusy((b) => [...b, file.name]);
      try {
        await api.upload(file);
        // Indexing continues on the server; the document list shows its progress and any error.
        // document_uploaded / document_indexed are system events fired by the engine after commit.
      } catch (e) {
        setError(`${file.name}: ${(e as Error).message}`);
      } finally {
        setBusy((b) => b.filter((n) => n !== file.name));
        props.onUploaded();
      }
    }
  }

  return (
    <Card>
      <CardTitle>დოკუმენტების ატვირთვა</CardTitle>
      <label
        class={[
          "flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors",
          { "border-stone-900 bg-stone-50": dragging(), "border-stone-300 hover:border-stone-500": !dragging() },
        ]}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(e.dataTransfer?.files ?? null);
        }}
      >
        <span class="text-sm font-medium">ჩააგდე ფაილები აქ ან აირჩიე</span>
        <span class="text-xs text-stone-500">PDF, Word, Excel, CSV, PowerPoint (ძველი .doc/.xls/.ppt-იც), ODT, RTF, TXT, HTML · მაქს. 15 MB</span>
        <span class="text-xs text-stone-400">Google Docs: File → Download → .docx</span>
        <input
          type="file"
          class="sr-only"
          multiple
          accept={ACCEPT}
          onChange={(e) => {
            upload(e.currentTarget.files);
            e.currentTarget.value = "";
          }}
        />
      </label>
      <For each={busy()}>
        {(name) => (
          <p class="mt-3 flex items-center gap-2 text-sm text-stone-600">
            <Spinner /> {name} — მუშავდება…
          </p>
        )}
      </For>
      <Show when={error()}>{(msg) => <p class="mt-3 text-sm text-red-600">{msg()}</p>}</Show>
    </Card>
  );
}
