import sys
import os
from io import BytesIO

# Add project root to path
sys.path.append(os.getcwd())

try:
    from backend.services.excel import ExcelService

    print("✅ Imported ExcelService")
except ImportError as e:
    print(f"❌ Failed to import ExcelService: {e}")
    sys.exit(1)

try:
    from bot.handlers.upload import handle_document

    print("✅ Imported bot.handlers.upload")
except ImportError as e:
    print(f"❌ Failed to import bot.handlers.upload: {e}")
    sys.exit(1)


# Test Excel parsing with ExcelService
def test_parsing():
    import openpyxl

    # Create dummy Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Артикул", "Название", "Количество"])
    ws.append(["TEST-123", "Test Product", 10])

    out = BytesIO()
    wb.save(out)
    out.seek(0)

    print("Testing parse_order_file...")
    items = ExcelService.parse_order_file(out, "test.xlsx")

    print(f"Parsed {len(items)} items")
    if len(items) == 1 and items[0].client_sku == "TEST-123":
        print("✅ Parse success")
    else:
        print(f"❌ Parse failed: {items}")

    # Test Export
    print("Testing export_order...")
    data = [
        {
            "client_sku": "TEST-123",
            "client_name": "Test Product",
            "quantity": 10,
            "match": {"product_sku": "MATCH-1", "confidence": 90},
        }
    ]
    exported = ExcelService.export_order(data)
    if len(exported) > 100:
        print("✅ Export success (bytes generated)")
    else:
        print("❌ Export failed (too small)")


if __name__ == "__main__":
    test_parsing()
