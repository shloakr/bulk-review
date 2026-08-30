"use client";

import { useState } from "react";
import { Review, ReviewEvent } from "@/lib/api";

/* Task Rows (Beautiful UI pattern): one row per pipeline stage.
 *   done    → green check badge + Completed pill
 *   active  → spinner ring with the stage number
 *   idle    → static ring with the stage number
 *   failed  → red cross badge + Failed pill
 * Rows expand to show stage details; the active row starts expanded. */

const STAGES = ["PLAN", "DISCOVER", "QUALIFY", "EXTRACT", "COMPLETE"] as const;

type Detail = { label: string; meta: string };
type RowState = "done" | "active" | "idle" | "failed";

function SpinnerRing({ active, children }: { active?: boolean; children?: React.ReactNode }) {
  const size = 24, stroke = 2;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <svg
        width={size} height={size} className="absolute inset-0"
        style={active ? { animation: "spin 1.1s linear infinite" } : undefined}
      >
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-line)" strokeWidth={stroke} />
        {active && (
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke="var(--color-brand)" strokeWidth={stroke} strokeLinecap="round"
            strokeDasharray={`${c * 0.28} ${c * 0.72}`}
          />
        )}
      </svg>
      <span className="relative text-[10.5px] font-semibold tabular-nums text-ink">{children}</span>
    </span>
  );
}

function Badge({ tone, children }: { tone: "red" | "green"; children: React.ReactNode }) {
  return (
    <span
      className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-white ${
        tone === "red" ? "bg-red-500" : "bg-brand"
      }`}
      style={{ animation: "pop-in 300ms cubic-bezier(0.23,1,0.32,1) both" }}
    >
      {children}
    </span>
  );
}

const CheckIcon = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
);
const XIcon = (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12" /></svg>
);

export default function ReviewProgress({
  review,
  events,
}: {
  review: Review;
  events: ReviewEvent[];
}) {
  const failed = review.status === "FAILED";
  const stageIdx = failed
    ? Math.max(STAGES.findIndex((s) => s === review.status), 0)
    : STAGES.indexOf(review.status as (typeof STAGES)[number]);
  const complete = review.status === "COMPLETE";
  const p = review.progress;
  const plan = review.plan;

  const extractEvents = events
    .filter((e) => e.stage === "EXTRACT" && e.data?.document_id)
    .slice(-3)
    .reverse();

  const rows: { key: string; num: number; label: string; amount: string; details: Detail[] }[] = [
    {
      key: "plan", num: 1,
      label: "Plan review",
      amount: plan ? `${plan.retrieval_queries.length} queries · ${plan.fields.length} fields` : "…",
      details: plan
        ? [
            ...plan.retrieval_queries.map((q, i) => ({ label: q, meta: `Q${i + 1}` })),
            { label: "Output columns", meta: plan.fields.map((f) => f.key).join(", ").slice(0, 48) },
          ]
        : [],
    },
    {
      key: "discover", num: 2,
      label: "Search the corpus",
      amount: p.candidates > 0 ? `${p.candidates} candidates` : "…",
      details: [
        { label: "Chunk-level hybrid search (dense + SPLADE, RRF)", meta: "all documents" },
        { label: "Candidate documents (recall-first)", meta: String(p.candidates || "—") },
      ],
    },
    {
      key: "qualify", num: 3,
      label: "Qualify candidates",
      amount: p.qualified_done > 0 ? `${p.qualified_relevant} relevant` : "…",
      details: [
        { label: "Candidates reviewed", meta: `${p.qualified_done}/${p.candidates || "—"}` },
        { label: "Judged in scope", meta: String(p.qualified_relevant) },
      ],
    },
    {
      key: "extract", num: 4,
      label: "Extract documents",
      amount: p.extract_total > 0 ? `${p.extract_done}/${p.extract_total} docs` : "…",
      details: [
        { label: "One bounded research session per document", meta: "≤8 tool calls" },
        ...extractEvents.map((e) => ({
          label: `Extracted ${e.data?.document_id}`,
          meta: new Date(e.ts * 1000).toLocaleTimeString(),
        })),
      ],
    },
  ];

  const stateFor = (i: number): RowState => {
    if (failed) return i < stageIdx ? "done" : i === stageIdx ? "failed" : "idle";
    if (complete) return "done";
    return i < stageIdx ? "done" : i === stageIdx ? "active" : "idle";
  };

  const [manualOpen, setManualOpen] = useState<Record<string, boolean>>({});

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-white">
      {rows.map((row, i) => {
        const state = stateFor(i);
        const open = manualOpen[row.key] ?? (state === "active" || state === "failed");
        return (
          <div
            key={row.key}
            className="border-b border-line/60 transition-colors last:border-0 hover:bg-paper/50"
            style={{ animation: `fade-up 450ms cubic-bezier(0.23,1,0.32,1) ${i * 80}ms both` }}
          >
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setManualOpen((cur) => ({ ...cur, [row.key]: !open }))}
              className="flex h-11 w-full items-center gap-2.5 px-3 text-left"
            >
              <span className="flex size-6 shrink-0 items-center justify-center">
                {state === "done" ? (
                  <Badge tone="green">{CheckIcon}</Badge>
                ) : state === "failed" ? (
                  <Badge tone="red">{XIcon}</Badge>
                ) : (
                  <SpinnerRing active={state === "active"}>{row.num}</SpinnerRing>
                )}
              </span>
              <span className={`min-w-0 flex-1 truncate text-[13px] font-medium ${state === "idle" ? "text-ink-soft/60" : "text-ink"}`}>
                {row.label}
              </span>
              <span className="text-[12.5px] tabular-nums text-ink-soft">{row.amount}</span>
              {state === "done" && (
                <span className="inline-flex h-[22px] items-center rounded-full bg-brand-tint/60 px-2 text-[11.5px] font-medium text-brand" style={{ animation: "fade-in 200ms ease-out both" }}>
                  Completed
                </span>
              )}
              {state === "failed" && (
                <span className="inline-flex h-[22px] items-center rounded-full bg-red-100 px-2 text-[11.5px] font-medium text-red-600" style={{ animation: "fade-in 200ms ease-out both" }}>
                  Failed
                </span>
              )}
              <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-full text-ink-soft/70">
                <svg
                  width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
                  className="transition-transform duration-300"
                  style={{ transform: open ? "rotate(180deg)" : "rotate(0)" }}
                >
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </span>
            </button>

            <div
              className="grid transition-[grid-template-rows,opacity] duration-300"
              style={{
                gridTemplateRows: open ? "1fr" : "0fr",
                opacity: open ? 1 : 0,
                transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)",
              }}
            >
              <div className="overflow-hidden">
                <div className="mb-2.5 grid grid-cols-[24px_1fr] gap-2.5 px-3">
                  <span aria-hidden className="mx-auto h-full w-px bg-line" />
                  <div className="flex flex-col gap-1.5 pr-2">
                    {row.details.map((d, j) => (
                      <div
                        key={`${d.label}-${j}`}
                        className="flex items-center justify-between gap-3"
                        style={
                          open
                            ? { animation: `fade-up 300ms cubic-bezier(0.23,1,0.32,1) ${120 + j * 80}ms both` }
                            : undefined
                        }
                      >
                        <span className="min-w-0 truncate text-[12px] text-ink-soft">{d.label}</span>
                        <span className="shrink-0 font-mono text-[11px] tabular-nums text-ink-soft/70">{d.meta}</span>
                      </div>
                    ))}
                    {row.details.length === 0 && (
                      <span className="text-[12px] text-ink-soft/60">Waiting…</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
      {failed && review.error && (
        <div className="border-t border-line bg-red-50 px-4 py-2 text-[12px] text-red-600">
          {review.error}
        </div>
      )}
    </div>
  );
}
