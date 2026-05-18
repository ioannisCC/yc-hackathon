"""Moss client. SDK-optional.

The Moss SDK requires the Rust `moss_core` binary, which has no Linux wheel,
so we can't install it on Railway. To keep the build green, we keep `moss`
out of requirements.txt and probe for it at import time:

  * If `moss` is importable (local dev), use it for create_index + in-memory query.
  * If not (Railway), we keep a REST-only surface:
      - validate_credentials()  — smoke
      - query(name, text, top_k) — cloud `/query` fallback
      - create_business_index    — raises NotImplementedError; caller must handle.

Onboarding logs a warning and continues with an empty moss_index_name when the
SDK is unavailable; lookup_business_info then falls back to an in-memory scan
over the stored BusinessInfo JSON.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_MANAGE_URL = "https://service.usemoss.dev/v1/manage"
_QUERY_URL = "https://service.usemoss.dev/query"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
DEFAULT_MODEL = "moss-minilm"
DEFAULT_TOP_K = 5
DEFAULT_ALPHA = 0.6


# ---------- SDK probe -----------------------------------------------------------

try:
    from moss import DocumentInfo as _SDKDocumentInfo  # type: ignore[import-not-found]
    from moss import MossClient as _SDKMossClient  # type: ignore[import-not-found]
    from moss import QueryOptions as _SDKQueryOptions  # type: ignore[import-not-found]

    HAS_SDK = True
except ImportError as _moss_import_err:
    HAS_SDK = False
    _SDKDocumentInfo = None  # type: ignore[assignment]
    _SDKMossClient = None  # type: ignore[assignment]
    _SDKQueryOptions = None  # type: ignore[assignment]
    # Surface the actual error so a Railway build that lost the wheel is
    # diagnosable from a single log line, not from "why is lookup_business_info
    # falling back to escalate_to_human in prod but not locally?"
    log.warning(
        "Moss SDK not available, will use REST fallback: %s", _moss_import_err,
    )

_sdk_client: Any = None


def _sdk() -> Any:
    global _sdk_client
    if _sdk_client is None and HAS_SDK:
        _sdk_client = _SDKMossClient(
            project_id=settings.MOSS_PROJECT_ID,
            project_key=settings.MOSS_PROJECT_KEY,
        )
    return _sdk_client


# ---------- REST primitives (always available) ----------------------------------


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-service-version": "v1",
        "x-project-key": settings.MOSS_PROJECT_KEY,
    }


async def _manage(action: str, **kwargs: Any) -> dict[str, Any]:
    body = {"action": action, "projectId": settings.MOSS_PROJECT_ID, **kwargs}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(_MANAGE_URL, json=body, headers=_headers())
        if r.status_code >= 400:
            raise RuntimeError(f"Moss {action} → {r.status_code}: {r.text}")
        return r.json()


async def validate_credentials() -> dict[str, Any]:
    """Pure-REST credential check — used by the smoke suite."""
    return await _manage("validateCredentials")


async def list_indexes() -> list[dict[str, Any]]:
    r = await _manage("listIndexes")
    return r if isinstance(r, list) else r.get("indexes", [])


async def _query_cloud(
    name: str, text: str, top_k: int = DEFAULT_TOP_K
) -> dict[str, Any]:
    body = {
        "query": text,
        "indexName": name,
        "projectId": settings.MOSS_PROJECT_ID,
        "projectKey": settings.MOSS_PROJECT_KEY,
        "topK": top_k,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(
            _QUERY_URL, json=body, headers={"Content-Type": "application/json"}
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Moss query → {r.status_code}: {r.text[:200]}")
        return r.json()


# ---------- Public API ----------------------------------------------------------


async def query(
    name: str, text: str, top_k: int = DEFAULT_TOP_K
) -> dict[str, Any]:
    """Returns {docs: [{id, text, score, metadata}], ...}.

    Prefers the SDK's in-memory path when available; falls back to the cloud /query endpoint."""
    if HAS_SDK:
        try:
            options = _SDKQueryOptions(top_k=top_k, alpha=DEFAULT_ALPHA)
            result = await _sdk().query(name, text, options)
            docs = [
                {
                    "id": getattr(d, "id", ""),
                    "text": getattr(d, "text", ""),
                    "score": getattr(d, "score", 0.0),
                    "metadata": getattr(d, "metadata", None),
                }
                for d in (getattr(result, "docs", None) or [])
            ]
            return {"docs": docs}
        except Exception as e:
            log.warning("Moss SDK query failed, falling back to cloud: %s", e)
    return await _query_cloud(name, text, top_k)


async def create_business_index(
    index_name: str, documents: list[dict[str, Any]]
) -> str:
    """Create + load an index. Requires the SDK (Rust binary). Raises on REST-only deploys."""
    if not HAS_SDK:
        raise NotImplementedError(
            "Moss index creation requires the SDK (moss_core Rust binary). "
            "Skipping — lookup_business_info will fall back to in-memory scan."
        )
    sdk_docs = [
        _SDKDocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata"))
        for d in documents
    ]
    await _sdk().create_index(index_name, sdk_docs, model_id=DEFAULT_MODEL)
    await _sdk().load_index(index_name)
    return index_name


async def delete_index(index_name: str) -> None:
    if HAS_SDK:
        try:
            await _sdk().delete_index(index_name)
            return
        except Exception as e:
            log.warning("SDK delete failed; trying REST: %s", e)
    try:
        await _manage("deleteIndex", indexName=index_name)
    except Exception as e:
        log.warning("Moss delete_index(%s) failed: %s", index_name, e)
