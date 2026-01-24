import csv
from io import StringIO, BytesIO
import codecs


def create_sample_csv():
    """Create a sample CSV file in memory for testing."""
    content = "Артикул;Название;Количество\n101105032R;Муфта ППР 32;10\n202132110K;Ревизия кан. 110;5"
    return BytesIO(content.encode("utf-8"))  # CSVs are typically bytes when uploaded


def parse_csv_file(file, filename: str):
    """
    Parse CSV file using standard csv module (replacing pandas.read_csv).
    Returns list of dicts: {'sku': ..., 'name': ..., 'qty': ...}
    """
    print(f"Parsing {filename}...")

    # Handle encoding detection (simplified for prototype)
    # In production we might loop through ['utf-8', 'cp1251']
    encodings = ["utf-8", "cp1251", "latin-1"]
    decoded_file = None

    file_content = file.read()

    for enc in encodings:
        try:
            decoded_file = StringIO(file_content.decode(enc))
            # Test read to check validity
            decoded_file.read(100)
            decoded_file.seek(0)
            print(f"Detected encoding: {enc}")
            break
        except UnicodeDecodeError:
            continue

    if not decoded_file:
        print("❌ Could not decode CSV")
        return []

    # Detect delimiter
    try:
        sample = decoded_file.read(1024)
        decoded_file.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        print(f"Detected delimiter: {repr(dialect.delimiter)}")
    except csv.Error:
        dialect = csv.excel
        print("⚠️ Could not detect dialect, using default Excel")

    reader = csv.reader(decoded_file, dialect)

    try:
        header = next(reader)
    except StopIteration:
        return []

    print(f"Headers: {header}")

    # Detect columns
    sku_col_idx = -1
    name_col_idx = -1
    qty_col_idx = -1

    for idx, val in enumerate(header):
        val = val.lower().strip()
        if any(x in val for x in ["артикул", "sku", "код", "арт"]):
            sku_col_idx = idx
        elif any(x in val for x in ["название", "наименование", "name", "товар"]):
            name_col_idx = idx
        elif any(x in val for x in ["количество", "кол-во", "qty", "шт"]):
            qty_col_idx = idx

    print(f"Columns found: SKU={sku_col_idx}, Name={name_col_idx}, Qty={qty_col_idx}")

    items = []
    for row in reader:
        if not row:
            continue

        sku = (
            str(row[sku_col_idx]).strip()
            if sku_col_idx != -1 and sku_col_idx < len(row)
            else ""
        )
        name = (
            str(row[name_col_idx]).strip()
            if name_col_idx != -1 and name_col_idx < len(row)
            else ""
        )
        qty_val = (
            row[qty_col_idx] if qty_col_idx != -1 and qty_col_idx < len(row) else 1
        )

        try:
            qty = float(qty_val) if qty_val else 1.0
        except ValueError:
            qty = 1.0

        if sku or name:
            items.append({"sku": sku, "name": name, "qty": qty})

    return items


def test_prototype():
    csv_file = create_sample_csv()
    items = parse_csv_file(csv_file, "order.csv")

    print(f"\nParsed {len(items)} items:")
    for item in items:
        print(item)

    assert len(items) == 2
    assert items[0]["sku"] == "101105032R"
    assert items[0]["qty"] == 10.0
    print("\n✅ Verification passed!")


if __name__ == "__main__":
    test_prototype()
