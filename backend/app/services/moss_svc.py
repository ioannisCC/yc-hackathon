"""Moss — per-business knowledge index (services, hours, prices, FAQ)."""
from __future__ import annotations

from moss import DocumentInfo, MossClient, QueryOptions

from app.config import settings

DEFAULT_MODEL = "moss-minilm"
DEFAULT_TOP_K = 4
DEFAULT_ALPHA = 0.6

_client: MossClient | None = None


def client() -> MossClient:
    global _client
    if _client is None:
        _client = MossClient(
            project_id=settings.MOSS_PROJECT_ID,
            project_key=settings.MOSS_PROJECT_KEY,
        )
    return _client


async def create_business_index(
    index_name: str, docs: list[DocumentInfo]
) -> str:
    await client().create_index(index_name, docs, model_id=DEFAULT_MODEL)
    await client().load_index(index_name)
    return index_name


async def query(index_name: str, q: str, top_k: int = DEFAULT_TOP_K) -> list[str]:
    """Return the top text snippets for a natural-language question."""
    result = await client().query(index_name, q, QueryOptions(top_k=top_k))
    return [d.text for d in (result.docs or [])]


async def delete_index(index_name: str) -> None:
    try:
        await client().delete_index(index_name)
    except Exception:
        pass
