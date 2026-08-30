"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import { api, DocResult, Review, ReviewEvent } from "@/lib/api";
import ReviewProgress from "@/components/review-progress";
import ResultsTable, { CellSelection } from "@/components/results-table";
import CitationPanel from "@/components/citation-panel";
import EvalSummary from "@/components/eval-summary";
import { useSidebar } from "@/components/app-shell";

export default function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { collapsed } = useSidebar();
  const [review, setReview] = useState<Review | null>(null);
  const [results, setResults] = useState<DocResult[]>([]);
  const [events, setEvents] = useState<ReviewEvent[]>([]);
  const [selection, setSelection] = useState<CellSelection | null>(null);
  const lastEvent = useRef(0);

  const poll = useCallback(async () => {
    try {
      const r = await api.getReview(id);
      setReview(r);
      const ev = await api.getEvents(id, lastEvent.current);
      if (ev.events.length) {
        lastEvent.current = ev.events[ev.events.length - 1].id;
        setEvents((prev) => {
          const seen = new Set(prev.map((e) => e.id));
          return [...prev, ...ev.events.filter((e) => !seen.has(e.id))].slice(-50);
        });
      }
      if (["EXTRACT", "COMPLETE", "FAILED"].includes(r.status)) {
        const res = await api.getResults(id);
        setResults(res.results);
      }
      return r.status;
    } catch {
      return null;
    }
  }, [id]);

  useEffect(() => {
    let stop = false;
    const loop = async () => {
      const status = await poll();
      if (stop) return;
      if (status === "COMPLETE" || status === "FAILED") return;
      setTimeout(loop, 1200);
    };
    loop();
    return () => {
      stop = true;
    };
  }, [poll]);

  if (!review)
    return (
      <div className="p-10 text-sm text-ink-soft">Loading review…</div>
    );

  const done = review.status === "COMPLETE";
  const extracted = results.filter((r) => r.status === "done").length;

  return (
    <div className="px-8 py-8">
      <div className={`mx-auto transition-[max-width] duration-300 ${collapsed ? "max-w-[1800px]" : "max-w-6xl"}`}>
        <h1 className="text-xl font-semibold tracking-tight">
          {review.name || "Bulk review"}
        </h1>
        <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-ink-soft">
          {review.prompt}
        </p>

        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)]">
          <ReviewProgress review={review} events={events} />
        </div>

        {results.length > 0 && review.plan && (
          <>
            <div className="mb-2 mt-6 flex items-baseline justify-between">
              <h2 className="text-[15px] font-semibold">
                Results · one row per relevant document
              </h2>
              <span className="text-[12px] text-ink-soft">
                {extracted}/{results.length} extracted
              </span>
            </div>
            <ResultsTable
              fields={review.plan.fields}
              results={results}
              onSelect={setSelection}
              selected={selection}
            />
          </>
        )}

        {done && (
          <div className="mt-6">
            <EvalSummary reviewId={id} />
          </div>
        )}
      </div>

      {selection && (
        <CitationPanel selection={selection} onClose={() => setSelection(null)} />
      )}
    </div>
  );
}
