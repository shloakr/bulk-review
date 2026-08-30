"use client";

import { useState } from "react";
import { DocResult, FieldDef, FieldResult } from "@/lib/api";

/** True when extraction found no substantive content (booleans excluded:
 *  a bare "No" on a comparison field with nothing else found is still empty). */
function isEmptyRow(r: DocResult, fields: FieldDef[]): boolean {
  if (r.status !== "done" || !r.fields) return false;
  const substantive = fields.filter((f) => f.type !== "boolean");
  return (
    substantive.length > 0 &&
    substantive.every((f) => {
      const fr = r.fields![f.key];
      return !fr || fr.status === "not_found" || fr.value == null;
    })
  );
}

export type CellSelection = {
  doc: DocResult;
  fieldKey: string;
  field: FieldResult;
  label: string;
};

export default function ResultsTable({
  fields,
  results,
  onSelect,
  selected,
}: {
  fields: FieldDef[];
  results: DocResult[];
  onSelect: (sel: CellSelection) => void;
  selected: CellSelection | null;
}) {
  const [showEmpty, setShowEmpty] = useState(false);

  if (results.length === 0)
    return (
      <div className="rounded-2xl border border-line bg-white p-8 text-center text-sm text-ink-soft">
        Results will appear here as documents are extracted.
      </div>
    );

  const empty = results.filter((r) => isEmptyRow(r, fields));
  const shown = showEmpty ? results : results.filter((r) => !isEmptyRow(r, fields));

  return (
    <div className="overflow-x-auto rounded-2xl border border-line bg-white">
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-line bg-paper/60 text-[11px] uppercase tracking-wide text-ink-soft">
            <th className="px-4 py-2.5 font-semibold">Document</th>
            {fields.map((f) => (
              <th key={f.key} className="px-4 py-2.5 font-semibold">
                {f.label}
              </th>
            ))}
            <th className="px-4 py-2.5 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.document_id} className="border-b border-line/60 last:border-0">
              <td className="whitespace-nowrap px-4 py-2.5 font-medium">
                {r.document_id}
              </td>
              {fields.map((f) => (
                <td key={f.key} className="max-w-56 px-4 py-2.5 align-top">
                  {r.fields?.[f.key] ? (
                    <CellValue
                      field={r.fields[f.key]}
                      isSelected={
                        selected?.doc.document_id === r.document_id &&
                        selected?.fieldKey === f.key
                      }
                      onClick={() =>
                        onSelect({
                          doc: r,
                          fieldKey: f.key,
                          field: r.fields![f.key],
                          label: f.label,
                        })
                      }
                    />
                  ) : (
                    <span className="text-ink-soft/50">
                      {r.status === "running" ? <Shimmer /> : "—"}
                    </span>
                  )}
                </td>
              ))}
              <td className="whitespace-nowrap px-4 py-2.5">
                <RowStatus status={r.status} error={r.error} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {empty.length > 0 && (
        <button
          onClick={() => setShowEmpty((v) => !v)}
          className="w-full border-t border-line px-4 py-2.5 text-left text-[12px] text-ink-soft hover:bg-paper"
        >
          {showEmpty ? "▾" : "▸"} {empty.length} document
          {empty.length === 1 ? "" : "s"} with no extractable content (
          {empty.map((r) => r.document_id).join(", ")}) — click to{" "}
          {showEmpty ? "hide" : "show"}
        </button>
      )}
    </div>
  );
}

function CellValue({
  field,
  onClick,
  isSelected,
}: {
  field: FieldResult;
  onClick: () => void;
  isSelected: boolean;
}) {
  const ring = isSelected ? "ring-2 ring-accent/60" : "";
  if (field.status === "not_found")
    return (
      <button onClick={onClick} className={`rounded-md bg-gray-100 px-2 py-0.5 text-[12px] text-ink-soft ${ring}`}>
        Not found
      </button>
    );
  if (field.status === "conflicting")
    return (
      <button onClick={onClick} className={`rounded-md bg-warm-tint/60 px-2 py-0.5 text-[12px] font-medium text-warm ${ring}`}>
        Conflicting
      </button>
    );
  if (field.status === "uncertain")
    return (
      <button onClick={onClick} className={`rounded-md bg-accent-tint/40 px-2 py-0.5 text-[12px] text-accent ${ring}`}>
        Uncertain{field.value != null ? `: ${short(field.value)}` : ""}
      </button>
    );
  if (typeof field.value === "boolean")
    return (
      <button
        onClick={onClick}
        className={`rounded-md px-2 py-0.5 text-[12px] font-semibold ${ring} ${
          field.value
            ? "bg-warm-tint/60 text-warm"
            : "bg-brand-tint/60 text-brand"
        }`}
      >
        {field.value ? "Yes" : "No"}
      </button>
    );
  return (
    <button
      onClick={onClick}
      className={`rounded-md text-left leading-snug underline decoration-line decoration-dotted underline-offset-2 hover:decoration-accent ${ring}`}
      title="Click to inspect evidence"
    >
      {short(field.value)}
    </button>
  );
}

function short(v: string | string[] | boolean | number | null): string {
  if (v == null) return "—";
  const s = Array.isArray(v) ? v.join(", ") : String(v);
  return s.length > 90 ? s.slice(0, 90) + "…" : s;
}

function RowStatus({ status, error }: { status: string; error: string | null }) {
  const map: Record<string, string> = {
    pending: "bg-gray-100 text-ink-soft",
    running: "bg-accent-tint/50 text-accent",
    done: "bg-brand-tint/60 text-brand",
    failed: "bg-red-100 text-red-600",
  };
  return (
    <span
      title={error || undefined}
      className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${map[status]}`}
    >
      {status}
    </span>
  );
}

function Shimmer() {
  return <span className="inline-block h-3 w-20 animate-pulse rounded bg-gray-200" />;
}
