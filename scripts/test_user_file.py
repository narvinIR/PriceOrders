import sys
import os
from backend.services.excel import ExcelService

# Add project root to path
sys.path.append(os.getcwd())

FILE_PATH = "/home/dimas/projects/PriceOrders/zakaz_jakko_ready.xlsx"


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
            print("🔍 First 5 items:")
            for item in items[:5]:
                print(
                    f"  - SKU: '{item.client_sku}' | Name: '{item.client_name}' | Qty: {item.quantity}"
                )
        else:
            print("⚠️ No items found! Check column names.")

    except Exception as e:
        print(f"❌ Error parsing file: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_file()
