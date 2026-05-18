# Moss integration status (for production merge)

- Moss SDK requires `inferedge-moss-core` Rust binary
- `moss 1.1.0` pins `inferedge-moss-core==0.11.0` which isn't published
  on PyPI Linux (verified 2026-05-18, only 0.1.0-0.4.1 available)
- This means the SDK only works locally on Mac via uv's cached resolution
- Production uses REST fallback in `moss_svc._query_cloud` (currently
  returns 503 from Moss cloud — may be transient or endpoint stale)
- When Moss is unreachable, `lookup_business_info` gracefully falls back
  to in-memory keyword scan over `business.extra.scraped` data
- When that's also empty (manual DB inserts), the agent escalates to
  human via `escalate_to_human` — clean degraded behavior

## To enable Moss in production later

- **Option 1**: wait for Moss to publish `inferedge-moss-core` on PyPI Linux
- **Option 2**: contact Moss team for self-hosted binary or alternate distro
- **Option 3**: fix `_query_cloud` URL/auth (REST endpoint returns 503 —
  may need different headers or endpoint URL — reach out via Moss Discord)

The Moss index `codesalon-1bd9af6c` exists in Moss cloud (seeded locally),
so when the REST endpoint works, no re-seeding needed.

## Local seeding

```bash
cd backend
uv sync --extra local        # installs Moss SDK (Mac wheel)
uv run python scripts/seed_code_salon_moss.py
```

## Production install

```bash
# Railway runs `uv sync` (no --extra local) — Moss SDK is skipped.
# moss_svc.HAS_SDK = False; the warning fires once on startup:
#   "Moss SDK not available, will use REST fallback: <ImportError>"
```
