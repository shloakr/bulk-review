"use client";

import { useState } from "react";
import { api, Evaluation } from "@/lib/api";
import InfoTip from "./info-tip";

export default function EvalSummary({ reviewId }: { reviewId: string }) {
  const [ev, setEv] = useState<Evaluation | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setEv(await api.evaluate(reviewId));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[13px] font-semibold">
          Evaluation vs hidden ground truth
          {ev && (
            <span className="rounded-full bg-accent-tint/40 px-2 py-0.5 text-[11px] font-medium text-accent">
              matched test set: {ev.test}
            </span>
          )}
        </div>
        <button
          onClick={run}
          disabled={busy}
          className="rounded-lg bg-ink px-3 py-1.5 text-[12px] font-medium text-white hover:bg-ink/85 disabled:opacity-40"
        >
          {busy ? "Evaluating…" : ev ? "Re-run" : "Run evaluation"}
        </button>
      </div>
      {err && <div className="mt-2 text-[12px] text-red-600">{err}</div>}
      {ev && (
        <div className="mt-3 grid grid-cols-3 gap-2.5">
          <Metric
            label="Candidate recall"
            v={ev.discovery.candidate_recall}
            tip="Of this test's ground-truth documents, the share that made it into the broad discovery candidate set (Stage B). A document missed here can never be recovered by later stages, so this is the primary retrieval metric."
          />
          <Metric
            label="Qualified recall"
            v={ev.discovery.qualified_recall}
            tip="Share of ground-truth documents that survived GPT qualification (Stage C) and went on to extraction."
          />
          <Metric
            label="Final precision"
            v={ev.discovery.final_precision}
            tip="Of the documents that produced actual extracted content (empty all-not-found rows excluded), the share that are true positives. This is the precision of what you read in the table."
          />
          <Metric
            label="Field accuracy"
            v={ev.extraction.overall_field_accuracy}
            tip="Share of extracted field values that match the ground truth, across all four fields on the ground-truth documents."
          />
          <Metric
            label="Citation page accuracy"
            v={ev.citations.citation_page_accuracy}
            tip="For fields marked found, how often at least one cited page is among the pages where the ground truth says the evidence actually lives."
          />
          <Metric
            label="Citation coverage"
            v={ev.citations.citation_coverage}
            tip="Share of found claims backed by at least one server-validated citation (the cited chunk exists, belongs to this document, and was actually shown to the model by a tool)."
          />
          <Metric
            label="Qualified precision"
            v={ev.discovery.qualified_precision}
            tip="Share of qualified documents that are true positives, before extraction weeds out documents with nothing to extract. Kept for diagnostics; Final precision is the headline number."
          />
        </div>
      )}
      {ev && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {Object.entries(ev.extraction.per_field).map(([k, f]) => (
            <span
              key={k}
              className="rounded-full bg-paper px-2.5 py-1 text-[11px] text-ink-soft ring-1 ring-line"
            >
              {k}: {f.accuracy == null ? "n/a" : `${(100 * f.accuracy).toFixed(0)}%`}{" "}
              ({f.correct}/{f.total})
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  v,
  tip,
}: {
  label: string;
  v: number | null | undefined;
  tip: string;
}) {
  return (
    <div className="rounded-xl bg-paper px-3 py-2.5 ring-1 ring-line">
      <div className="flex items-center gap-1.5 text-[11px] text-ink-soft">
        {label} <InfoTip text={tip} />
      </div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums">
        {v == null ? "n/a" : `${(100 * v).toFixed(1)}%`}
      </div>
    </div>
  );
}
