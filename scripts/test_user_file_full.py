import sys
import os
from backend.services.excel import ExcelService

# Add project root to path
sys.path.append(os.getcwd())

FILE_PATH = "/home/dimas/projects/PriceOrders/jakko_order_20260124_081218.xlsx"
from backend.services.matching import MatchingService


def test_file():
    if not os.path.exists(FILE_PATH):
        print(f"❌ File not found: {FILE_PATH}")
        return

    print(f"📂 Parsing: {FILE_PATH}")
    try:
        with open(FILE_PATH, "rb") as f:
            items = ExcelService.parse_order_file(f, FILE_PATH)

        print(f"✅ Successfully parsed {len(items)} items")
        if items:
            print(
                f"🔍 Processing {len(items)} items with Cloud LLM Router (Google/Groq)...\n"
            )

            matcher = MatchingService()

            # Counter
            stats = {"exact": 0, "fuzzy": 0, "llm": 0, "not_found": 0}

            print(
                f"{'QTY':<5} | {'SKU':<15} | {'CLIENT NAME':<50} | {'MATCHED NAME':<50} | {'TYPE':<10} | {'CONF'}"
            )
            print("-" * 150)

            for item in items:
                # Run matching
                result = matcher.match_item(
                    client_id=None,  # No client cache for test
                    client_sku=item.client_sku,
                    client_name=item.client_name,
                )

                # Update stats
                match_type = result.match_type
                if "llm" in match_type:
                    stats["llm"] += 1
                elif "exact" in match_type:
                    stats["exact"] += 1
                elif "fuzzy" in match_type:
                    stats["fuzzy"] += 1
                else:
                    stats["not_found"] += 1

                # Print details
                # Print details
                qty = item.quantity or 0
                sku_disp = (item.client_sku or "")[:15]
                client_name_disp = (item.client_name or "")[:50]
                matched_name = (result.product_name or "---")[:50]

                status_icon = "✅" if result.product_id else "❌"
                if "llm" in match_type:
                    status_icon = "🤖"

                print(
                    f"{qty:<5} | {sku_disp:<15} | {client_name_disp:<50} | {matched_name:<50} | {match_type:<10} | {result.confidence}% {status_icon}"
                )

            print("\n📊 FINAL STATS:")
            print(f"  Exact: {stats['exact']}")
            print(f"  Fuzzy: {stats['fuzzy']}")
            print(f"  LLM:   {stats['llm']}  <-- Cloud Router Matches")
            print(f"  Lost:  {stats['not_found']}")

        else:
            print("⚠️ No items found! Check column names.")

    except Exception as e:
        print(f"❌ Error parsing file: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_file()
