"use client";

import { Review, ReviewEvent } from "@/lib/api";

const STAGES = ["PLAN", "DISCOVER", "QUALIFY", "EXTRACT", "COMPLETE"] as const;

export default function ReviewProgress({
  review,
  events,
}: {
  review: Review;
  events: ReviewEvent[];
}) {
  const stageIdx = STAGES.indexOf(review.status as (typeof STAGES)[number]);
  const failed = review.status === "FAILED";
  const p = review.progress;

  const rows = [
    {
      stage: "PLAN",
      label:
        review.plan
          ? `Planned ${review.plan.retrieval_queries.length} retrieval queries · ${review.plan.fields.length} output fields`
          : "Planning review",
    },
    {
      stage: "DISCOVER",
      label:
        p.candidates > 0
          ? `Searched the corpus → ${p.candidates} candidate documents`
          : "Searching all documents",
    },
    {
      stage: "QUALIFY",
      label:
        p.candidates > 0
          ? `Qualifying ${p.qualified_done} / ${p.candidates} candidates · ${p.qualified_relevant} relevant`
          : "Qualifying candidates",
    },
    {
      stage: "EXTRACT",
      label:
        p.extract_total > 0
          ? `Extracting ${p.extract_done} / ${p.extract_total} documents`
          : "Extracting relevant documents",
    },
  ];

  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      {/* Task Rows */}
      <div className="space-y-2.5">
        {rows.map((r, i) => {
          const state = failed
            ? i < stageIdx
              ? "done"
              : "idle"
            : review.status === "COMPLETE" || i < stageIdx
              ? "done"
              : i === stageIdx
                ? "active"
                : "idle";
          return (
            <div key={r.stage} className="flex items-center gap-3">
              <StageIcon state={state} />
              <span
                className={`text-[13px] ${
                  state === "idle" ? "text-ink-soft/60" : "text-ink"
                } ${state === "active" ? "font-medium" : ""}`}
              >
                {r.label}
              </span>
            </div>
          );
        })}
        {failed && (
          <div className="flex items-center gap-3">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-[11px] text-red-600">
              ✕
            </span>
            <span className="text-[13px] text-red-600">
              {review.error || "Review failed"}
            </span>
          </div>
        )}
      </div>

      {/* Tool Chips from recent events */}
      {review.plan && (
        <div className="mt-4 flex flex-wrap gap-1.5 border-t border-line pt-3">
          {review.plan.retrieval_queries.map((q) => (
            <span
              key={q}
              className="rounded-full bg-accent-tint/40 px-2.5 py-1 text-[11px] text-accent"
              title="Hybrid retrieval query"
            >
              ⌕ {q.length > 46 ? q.slice(0, 46) + "…" : q}
            </span>
          ))}
        </div>
      )}
      {events.length > 0 && (
        <div className="mt-3 max-h-24 space-y-1 overflow-y-auto text-[11.5px] text-ink-soft">
          {events.slice(-6).map((e) => (
            <div key={e.id} className="flex gap-2">
              <span className="shrink-0 font-medium text-ink-soft/70">
                {e.stage}
              </span>
              <span className="truncate">{e.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StageIcon({ state }: { state: "done" | "active" | "idle" }) {
  if (state === "done")
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-tint text-[11px] font-bold text-brand">
        ✓
      </span>
    );
  if (state === "active")
    return (
      <span className="relative flex h-5 w-5 items-center justify-center">
        <span className="absolute h-4 w-4 animate-ping rounded-full bg-accent/30" />
        <span className="h-2.5 w-2.5 rounded-full bg-accent" />
      </span>
    );
  return <span className="h-5 w-5 rounded-full border-2 border-line" />;
}
