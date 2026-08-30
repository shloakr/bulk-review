export type FieldDef = {
  key: string;
  label: string;
  type: "string" | "string[]" | "boolean" | "number";
  instruction: string;
};

export type Plan = {
  review_name: string;
  document_scope: string;
  retrieval_queries: string[];
  fields: FieldDef[];
};

export type Review = {
  review_id: string;
  prompt: string;
  name: string | null;
  status: "PLAN" | "DISCOVER" | "QUALIFY" | "EXTRACT" | "COMPLETE" | "FAILED";
  plan: Plan | null;
  error: string | null;
  created_at: number;
  progress: {
    candidates: number;
    qualified_done: number;
    qualified_relevant: number;
    extract_done: number;
    extract_total: number;
  };
};

export type Citation = {
  chunk_id: string;
  document_id: string;
  page: number;
  text: string;
  bbox: number[] | null;
};

export type FieldResult = {
  value: string | string[] | boolean | number | null;
  status: "found" | "not_found" | "conflicting" | "uncertain";
  citation_ids: string[];
  citations: Citation[];
  note: string | null;
};

export type DocResult = {
  document_id: string;
  status: "pending" | "running" | "done" | "failed";
  fields: Record<string, FieldResult> | null;
  tool_calls: { tool: string; arg: string }[];
  error: string | null;
};

export type ReviewEvent = {
  id: number;
  ts: number;
  stage: string;
  message: string;
  data: Record<string, unknown> | null;
};

export type CorpusStatus = {
  pdfs: number;
  indexed_documents: number;
  chunks: number;
};

export type Evaluation = {
  test: string;
  discovery: {
    candidate_recall: number | null;
    qualified_recall: number | null;
    qualified_precision: number | null;
    final_precision: number | null;
    substantive_documents: number;
    candidates: number;
    qualified: number;
  };
  extraction: {
    overall_field_accuracy: number | null;
    per_field: Record<
      string,
      { accuracy: number | null; correct: number; total: number }
    >;
  };
  citations: {
    citation_field_hit_rate: number | null;
    citation_precision: number | null;
    fields_all_citations_expected: number | null;
    citation_coverage: number | null;
  };
};

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  corpusStatus: () => fetch("/api/corpus/status").then((r) => j<CorpusStatus>(r)),
  createReview: (prompt: string) =>
    fetch("/api/reviews", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    }).then((r) => j<{ review_id: string }>(r)),
  listReviews: () =>
    fetch("/api/reviews").then((r) => j<{ reviews: Review[] }>(r)),
  getReview: (id: string) => fetch(`/api/reviews/${id}`).then((r) => j<Review>(r)),
  getResults: (id: string) =>
    fetch(`/api/reviews/${id}/results`).then((r) => j<{ results: DocResult[] }>(r)),
  getEvents: (id: string, after = 0) =>
    fetch(`/api/reviews/${id}/events?after=${after}`).then((r) =>
      j<{ events: ReviewEvent[] }>(r)
    ),
  evaluate: (id: string) =>
    fetch(`/api/evaluate/${id}`, { method: "POST" }).then((r) => j<Evaluation>(r)),
};
