"""OpenAI Responses API helpers (async client + strict structured output)."""

from __future__ import annotations

import json
from functools import lru_cache

from openai import AsyncOpenAI

from ..config import get_settings


@lru_cache
def client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key)


def strict_schema(name: str, schema: dict) -> dict:
    return {
        "format": {
            "type": "json_schema",
            "name": name,
            "strict": True,
            "schema": schema,
        }
    }


async def structured_call(model: str, system: str, user: str, name: str, schema: dict) -> dict:
    resp = await client().responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        text=strict_schema(name, schema),
    )
    return json.loads(resp.output_text)
