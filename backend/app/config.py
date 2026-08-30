from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # repo root
load_dotenv(ROOT / ".env")


class Settings:
    root: Path = ROOT
    data_dir: Path = ROOT / "data"
    corpus_dir: Path = ROOT / "data" / "corpus"
    sqlite_path: Path = ROOT / "data" / "app.db"

    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    planner_model: str = os.environ.get("OPENAI_PLANNER_MODEL", "gpt-5.6-terra")
    qualifier_model: str = os.environ.get("OPENAI_QUALIFIER_MODEL", "gpt-5.6-luna")
    extractor_model: str = os.environ.get("OPENAI_EXTRACTOR_MODEL", "gpt-5.6-terra")
    embedding_model: str = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    embedding_dim: int = 3072

    qdrant_url: str = os.environ.get("QDRANT_URL", "").strip()
    qdrant_local_path: Path = ROOT / os.environ.get("QDRANT_LOCAL_PATH", ".qdrant_local")
    collection: str = "regulatory_chunks"
    sparse_model_name: str = "prithivida/Splade_PP_en_v1"

    max_model_concurrency: int = int(os.environ.get("MAX_MODEL_CONCURRENCY", "5"))
    max_tool_calls_per_doc: int = int(os.environ.get("MAX_TOOL_CALLS_PER_DOC", "8"))
    candidate_doc_budget: int = int(os.environ.get("CANDIDATE_DOC_BUDGET", "100"))

    # discovery tuning (spec §15)
    dense_prefetch: int = 200
    sparse_prefetch: int = 200
    fused_limit: int = 200
    rrf_k: int = 60

    # per-document tool bounds (spec §20)
    max_search_top_k: int = 10
    max_find_hits: int = 20
    max_pages_per_open: int = 3

    # qualification evidence bundle size (spec §17)
    qualify_evidence_chunks: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
