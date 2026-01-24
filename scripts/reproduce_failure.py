import asyncio
import pandas as pd
from uuid import UUID
from backend.services.matching import MatchingService
from backend.services.excel import ExcelService


async def main():
    file_path = "/home/dimas/projects/PriceOrders/jakko_order_20260124_081218.xlsx"
    print(f"Testing matching on: {file_path}")

    # 1. Read file to mimic upload handler
    try:
        with open(file_path, "rb") as f:
            content = f.read()

        # 2. Extract data (similar to how handler does it, but we'll use ExcelService if available or just mock it)
        # Actually, let's look at how matching service is called in upload.py
        # It usually takes a list of strings or a dataframe.
        # Let's read it with pandas for simplicity as input
        df = pd.read_excel(file_path)
        # Assuming column 'Артикул клиента' has the names, as found in previous analysis
        items = df["Артикул клиента"].dropna().tolist()
        print(f"Loaded {len(items)} items.")

        # 3. Run Matching
        matcher = MatchingService()
        results = []
        # Use Elf client ID for consistency with upload.py
        elf_client_id = UUID("5013baff-4e85-448c-a8af-a90594407e43")

        # DEBUG: Process 5 items to check persistence
        items = items[:5]
        print(f"DEBUG: Processing {len(items)} items...")

        for i, item in enumerate(items):
            print(f"DEBUG: Matching item {i}: {item}")
            # item is just a string (sku) in this simple script
            res = matcher.match_item(
                client_id=elf_client_id, client_sku=item, client_name=item
            )
            print(f"DEBUG: Result {i}: {res.match_type}")
            # MatchingService returns MatchResult object
            results.append(
                {
                    "product_id": res.product_id,
                    "confidence": res.confidence,
                    "match_type": res.match_type,
                }
            )

        # 4. Analyze results
        matched_count = sum(1 for r in results if r.get("product_id"))
        print(f"Results: {matched_count}/{len(items)} matched.")

        if matched_count == 0:
            print("CRITICAL: 0 Matches found! Logic is broken.")
        else:
            print("Logic seems OK locally.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
