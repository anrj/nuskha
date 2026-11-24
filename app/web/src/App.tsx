import { createMemo, createSignal, Errored, Loading, onCleanup, refresh, Show } from "solid-js";
import { type Answer, type Citation, type Doc, api } from "./api";
import { track } from "./analytics";
import { AnswerView } from "./components/AnswerView";
import { AskPanel } from "./components/AskPanel";
import { DocumentList } from "./components/DocumentList";
import { UploadPanel } from "./components/UploadPanel";
import { Spinner } from "./components/ui";

export function App() {
  // Indexing runs on the server after upload: re-fetch while any document is still processing.
  let poll: ReturnType<typeof setTimeout> | undefined;
  const docs = createMemo(async () => {
    const list = await api.listDocuments();
    clearTimeout(poll);
    if (list.some((d) => d.status === "processing")) poll = setTimeout(() => refresh(docs), 2000);
    return list;
  });
  onCleanup(() => clearTimeout(poll));
  const [answer, setAnswer] = createSignal<Answer | null>(null);
  const [asking, setAsking] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  async function ask(question: string) {
    setAsking(true);
    setError(null);
    try {
      const res = await api.ask(question);
      track("QUESTION_ASKED", {
        question_id: res.question_id,
        question_length: question.length,
        latin_typed: /^[\x00-\x7F]*$/.test(question),
      });
      setAnswer(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAsking(false);
    }
  }

  async function deleteDocument(doc: Doc) {
    await api.deleteDocument(doc.id);
    // An answer citing the deleted file would now open nothing.
    if (answer()?.citations.some((c) => c.document_id === doc.id)) setAnswer(null);
    refresh(docs);
  }

  async function openSource(c: Citation) {
    const current = answer();
    if (!current) return;
    const tab = window.open("", "_blank"); // open synchronously so popup blockers allow it
    try {
      const opened = await api.openSource(current.question_id, c.chunk_id);
      track("SOURCE_OPENED", {
        source_open_id: opened.id,
        question_id: current.question_id,
        document_id: opened.document_id,
        page: opened.page,
        citation_rank: c.n,
      });
      const url = api.absolute(opened.url);
      if (tab) tab.location.href = url;
      else window.location.href = url;
    } catch (e) {
      tab?.close();
      setError((e as Error).message);
    }
  }

  return (
    <main class="mx-auto flex max-w-5xl flex-col gap-5 px-4 py-6 sm:py-10">
      <header>
        <h1 class="text-2xl font-bold tracking-tight">ნუსხა</h1>
        <p class="text-sm text-stone-600">ატვირთე დოკუმენტები და დასვი კითხვა — პასუხს მიიღებ წყაროს მითითებით.</p>
      </header>

      <AskPanel asking={asking()} onAsk={ask} />
      <Show when={error()}>{(msg) => <p class="text-sm text-red-600">{msg()}</p>}</Show>
      <Show when={answer()}>{(a) => <AnswerView answer={a()} onOpen={openSource} />}</Show>

      <div class="grid gap-5 md:grid-cols-[1fr_1.2fr]">
        <UploadPanel onUploaded={() => refresh(docs)} />
        <Errored fallback={(err) => <p class="text-sm text-red-600">ვერ ჩაიტვირთა: {String(err())}</p>}>
          <Loading fallback={<p class="flex items-center gap-2 text-sm text-stone-500"><Spinner /> იტვირთება…</p>}>
            <DocumentList docs={docs()} onDelete={deleteDocument} />
          </Loading>
        </Errored>
      </div>
    </main>
  );
}
