import pandas as pd

# Read the excel file
file_path = "/home/dimas/projects/PriceOrders/jakko_order_20260124_081218.xlsx"
df = pd.read_excel(file_path)

# Print summary
print(f"Total rows: {len(df)}")
print(f"Columns: {df.columns.tolist()}")

# Check for unmatched items
unmatched = df[df["Название поставщика"].isna()]
print(f"\nUnmatched items: {len(unmatched)}")

# Print first 20 matches for detailed inspection
print("\n--- MATCH COMPARISON (Request vs Answer) ---")
print(
    f"{'Client Request':<50} | {'Supplier Answer':<50} | {'Match %':<10} | {'Type':<15}"
)
print("-" * 135)

for index, row in df.iterrows():
    client_name = str(row["Название клиента"])[:48]
    supplier_name = str(row["Название поставщика"])[:48]
    match_score = row.get("Совпадение %", "N/A")
    match_type = row.get("Тип маппинга", "N/A")

    print(
        f"{client_name:<50} | {supplier_name:<50} | {match_score:<10} | {match_type:<15}"
    )
