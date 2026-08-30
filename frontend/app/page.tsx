"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, CorpusStatus } from "@/lib/api";

const DEFAULT_PROMPT =
  "Find the CMC excipient-control sections across the portfolio. For each relevant document, extract the excipient grade used, justification, guidance cited, and whether it contradicts the current specification.";

const PRESETS = [
  {
    label: "Test 1 · CMC excipient review",
    desc: "4 fields · 40 hidden positives",
    prompt: DEFAULT_PROMPT,
  },
  {
    label: "Test 2 · Stability protocols",
    desc: "6 fields · 20 hidden positives",
    prompt:
      "Take our stability protocols across the portfolio and for each one answer these six questions: what is the long-term storage condition, what are the testing timepoints, what stability acceptance criteria apply, were there any protocol deviations, what is the bracketing justification, and what post-approval stability commitment is made.",
  },
];

export default function Home() {
  const router = useRouter();
  const [corpus, setCorpus] = useState<CorpusStatus | null>(null);
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.corpusStatus().then(setCorpus).catch(() => {});
  }, []);

  const run = async (text: string) => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const { review_id } = await api.createReview(text.trim());
      router.push(`/reviews/${review_id}`);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  };
  const submit = () => run(prompt);

  return (
    <div className="mx-auto max-w-3xl px-8 pt-24">
      <h1 className="text-2xl font-semibold tracking-tight">
        Review your document portfolio
      </h1>
      <p className="mt-1.5 text-sm text-ink-soft">
        Describe what to find and what to extract. One structured row per
        relevant document, every claim cited to its source page.
      </p>

      {/* Prompt Bar */}
      <div className="mt-8 rounded-2xl border border-line bg-white p-3 shadow-sm focus-within:border-brand/50">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
          }}
          rows={4}
          className="w-full resize-none bg-transparent px-2 pt-1 text-[15px] leading-relaxed outline-none placeholder:text-ink-soft/60"
          placeholder="Find the CMC excipient-control sections across the portfolio and extract..."
        />
        <div className="flex items-center justify-between px-2 pb-1">
          <span className="text-[12px] text-ink-soft">
            {corpus
              ? `${corpus.indexed_documents} documents indexed · ${corpus.chunks.toLocaleString()} chunks`
              : "connecting to backend…"}
          </span>
          <button
            onClick={submit}
            disabled={busy || !prompt.trim()}
            className="rounded-xl bg-brand px-4 py-2 text-sm font-medium text-white transition hover:bg-brand/90 disabled:opacity-40"
          >
            {busy ? "Starting…" : "Run review"}
          </button>
        </div>
      </div>
      {error && (
        <div className="mt-3 rounded-lg bg-warm-tint/40 px-3 py-2 text-[13px] text-warm">
          {error}
        </div>
      )}

      {/* one-click benchmark reviews */}
      <div className="mt-4 grid grid-cols-2 gap-3">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            onClick={() => {
              setPrompt(p.prompt);
              run(p.prompt);
            }}
            disabled={busy}
            className="rounded-2xl border border-line bg-white p-4 text-left transition hover:border-brand/50 hover:shadow-sm disabled:opacity-40"
          >
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-semibold">{p.label}</span>
              <span className="rounded-full bg-brand-tint/50 px-2 py-0.5 text-[10.5px] font-medium text-brand">
                Run ▸
              </span>
            </div>
            <div className="mt-1 text-[12px] text-ink-soft">{p.desc}</div>
            <div className="mt-1.5 line-clamp-2 text-[11.5px] leading-snug text-ink-soft/70">
              {p.prompt}
            </div>
          </button>
        ))}
      </div>

      <div className="mt-10 grid grid-cols-3 gap-3">
        <Card
          label="Corpus"
          value={corpus ? String(corpus.pdfs) : "—"}
          sub="PDF documents"
        />
        <Card
          label="Indexed"
          value={corpus ? String(corpus.indexed_documents) : "—"}
          sub="parsed & embedded"
        />
        <Card
          label="Chunks"
          value={corpus ? corpus.chunks.toLocaleString() : "—"}
          sub="dense + SPLADE vectors"
        />
      </div>
    </div>
  );
}

function Card({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      <div className="text-[12px] text-ink-soft">{sub}</div>
    </div>
  );
}
