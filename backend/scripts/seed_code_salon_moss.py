"""One-time seed: create Moss index for Code Salon via SDK.

Run LOCALLY only — requires `uv sync --extra local` to install Moss SDK.
The created index lives in Moss cloud and is queryable from Railway via
REST fallback (if endpoint is reachable) or skipped gracefully via
lookup_business_info's fallback chain. See HANDOFF_NOTES.md.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services import moss_svc


INDEX_NAME = "codesalon-1bd9af6c"

DOCS = [
    {"id": "hours", "text": "Code Salon is open every day from 8am to 8pm Pacific time."},
    {"id": "address", "text": "Code Salon is located at 561 Castro Street, San Francisco, California."},
    {"id": "services-haircut", "text": "Haircut services: standard haircut (30 minutes), transformation haircut, barbering haircut, haircut with beard trim, haircut with full shave."},
    {"id": "services-color", "text": "Color services: full color, partial highlight, full highlight, balayage (partial and full), root touch-up, toner with blow out, grey blending, micro-foil highlight. Consultations required before any color service."},
    {"id": "services-extensions", "text": "Hair extensions offered in classic, hybrid, natural, volume, and mega volume bundles."},
    {"id": "services-treatments", "text": "Treatments: deep conditioning, express treatment, smoothing treatment, clear gloss."},
    {"id": "services-barbering", "text": "Barbering services: barbering haircut, beard trim, full shave, mustache trim, beard trim with shave."},
    {"id": "policies-booking", "text": "Bookings: consultations are required before scheduling color, texture, or special-occasion services. A 50 percent deposit is required at booking for hourly color and texture services."},
    {"id": "policies-cancellation", "text": "Cancellation policy: 48 hours notice required. Adjustments or cancellations made without 48-hour notice are charged 100 percent of the scheduled service price."},
    {"id": "policies-channels", "text": "Online booking is available 24 hours a day via Fresha. The salon also accepts appointments by phone during business hours."},
]


async def main():
    if not moss_svc.HAS_SDK:
        print("ERROR: moss SDK not installed.")
        print("Run: cd backend && uv add moss")
        sys.exit(1)

    print(f"SDK loaded. Creating Moss index '{INDEX_NAME}' with {len(DOCS)} docs...")
    try:
        result = await moss_svc.create_business_index(INDEX_NAME, DOCS)
        print(f"  ✓ created: {result}")
    except Exception as e:
        print(f"  ✗ creation failed: {e}")
        print("  Attempting to delete + retry...")
        try:
            await moss_svc.delete_index(INDEX_NAME)
            await asyncio.sleep(1)
            result = await moss_svc.create_business_index(INDEX_NAME, DOCS)
            print(f"  ✓ created after retry: {result}")
        except Exception as e2:
            print(f"  ✗ retry also failed: {e2}")
            raise

    print("\nWaiting 3 sec for index to be queryable...")
    await asyncio.sleep(3)

    print("Testing query 'what are your hours'...")
    res = await moss_svc.query(INDEX_NAME, "what are your hours")
    docs = res.get("docs") or []
    print(f"  Got {len(docs)} results:")
    for d in docs[:3]:
        score = d.get("score", 0.0)
        text = d.get("text", "")[:90]
        print(f"    - score={score:.3f}: {text}")

    print(f"\nTesting query 'what is your cancellation policy'...")
    res = await moss_svc.query(INDEX_NAME, "what is your cancellation policy")
    docs = res.get("docs") or []
    print(f"  Got {len(docs)} results:")
    for d in docs[:3]:
        score = d.get("score", 0.0)
        text = d.get("text", "")[:90]
        print(f"    - score={score:.3f}: {text}")

    print(f"\n✓ Seed complete. Now run this SQL in Railway Postgres:")
    print(f"  UPDATE businesses SET moss_index_name = '{INDEX_NAME}' WHERE id = '1bd9af6c-fcab-49f3-a2f7-fe915688d65e';")


if __name__ == "__main__":
    asyncio.run(main())