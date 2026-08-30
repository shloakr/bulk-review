"use client";

import { CellSelection } from "./results-table";

export default function CitationPanel({
  selection,
  onClose,
}: {
  selection: CellSelection;
  onClose: () => void;
}) {
  const { field, label, doc } = selection;
  return (
    <div className="fixed inset-y-0 right-0 z-20 flex w-[420px] flex-col border-l border-line bg-white shadow-2xl">
      <div className="flex items-start justify-between border-b border-line px-5 py-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">
            {label}
          </div>
          <div className="mt-1 text-[15px] font-semibold leading-snug">
            {renderValue(field.value, field.status)}
          </div>
          <div className="mt-0.5 text-[12px] text-ink-soft">
            {doc.document_id} · status: {field.status}
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg px-2 py-1 text-ink-soft hover:bg-paper"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {field.note && (
          <div className="rounded-xl bg-accent-tint/30 px-3.5 py-2.5 text-[12.5px] leading-relaxed text-ink">
            {field.note}
          </div>
        )}
        <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">
          Evidence · {field.citations.length} source
          {field.citations.length === 1 ? "" : "s"}
        </div>
        {field.citations.length === 0 && (
          <div className="text-[13px] text-ink-soft">
            No citations — this field was {field.status.replace("_", " ")}.
          </div>
        )}
        {field.citations.map((c) => (
          <div
            key={c.chunk_id}
            className="rounded-2xl border border-line bg-paper/50 p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-medium text-ink-soft">
                {c.document_id}.pdf · Page {c.page}
              </span>
              <a
                href={`/api/documents/${c.document_id}/pdf#page=${c.page}`}
                target="_blank"
                rel="noreferrer"
                className="rounded-lg bg-white px-2.5 py-1 text-[11.5px] font-medium text-accent ring-1 ring-line hover:ring-accent/50"
              >
                View source PDF ↗
              </a>
            </div>
            <blockquote className="mt-2.5 max-h-64 overflow-y-auto whitespace-pre-wrap border-l-2 border-brand/50 pl-3 text-[12.5px] leading-relaxed text-ink">
              {c.text}
            </blockquote>
            <div className="mt-2 font-mono text-[10.5px] text-ink-soft/70">
              {c.chunk_id}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderValue(
  v: string | string[] | boolean | number | null,
  status: string
) {
  if (v == null) return <span className="text-ink-soft">({status})</span>;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return Array.isArray(v) ? v.join(", ") : String(v);
}
