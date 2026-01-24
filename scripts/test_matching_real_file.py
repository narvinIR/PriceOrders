import sys
import os
import asyncio
from uuid import UUID

# Add project root to path
sys.path.append(os.getcwd())

from backend.services.excel import ExcelService
from backend.services.matching import MatchingService

import logging

logging.basicConfig(level=logging.INFO)  # Default INFO
logging.getLogger("backend").setLevel(logging.DEBUG)  # Enable DEBUG for backend
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

FILE_PATH = "/home/dimas/projects/PriceOrders/zakaz_jakko_ready.xlsx"
ELF_CLIENT_ID = UUID(
    "5013baff-4e85-448c-a8af-a90594407e43"
)  # Using Elf ID for cache test


async def test_matching():
    print(f"📂 Parsing: {FILE_PATH}")
    with open(FILE_PATH, "rb") as f:
        items = ExcelService.parse_order_file(f, FILE_PATH)

    print(f"✅ Parsed {len(items)} items. Initializing MatchingService...")
    matcher = MatchingService()

    # MatchingService loads strategies in __init__
    # Warmup happens automatically on first request or we can trigger it
    print("🚀 Starting matching...")
    results = []

    # Process sequentially for detailed output
    for i, item in enumerate(items):
        match_result = await asyncio.to_thread(
            matcher.match_item,
            client_id=ELF_CLIENT_ID,
            client_sku=item.client_sku,
            client_name=item.client_name,
        )
        results.append((item, match_result))

        status = "✅" if match_result.product_sku else "❌"
        conf = f"{match_result.confidence}%"
        print(
            f"{i+1:2d}. {status} [{conf}] {item.client_sku[:40]:<40} -> {match_result.product_sku or 'NOT FOUND'} ({match_result.match_type})"
        )

        # Rate limit protection for free tier (approx 15 RPM safe)
        if match_result.match_type in [
            "llm",
            "not_found",
            "hybrid",
        ]:  # Only sleep if we hit LLM/API likely
            await asyncio.sleep(4.0)
        else:
            await asyncio.sleep(0.1)  # Fast for exact matches

    # Stats
    found = sum(1 for _, r in results if r.product_sku)
    total = len(items)
    print(f"\n📊 Summary: Found {found}/{total} ({found/total*100:.1f}%)")


if __name__ == "__main__":
    asyncio.run(test_matching())
