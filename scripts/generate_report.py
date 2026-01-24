import pandas as pd
import sys
import os

if len(sys.argv) > 1:
    file_path = sys.argv[1]
else:
    file_path = "/home/dimas/projects/PriceOrders/jakko_order_20260124_081218.xlsx"

if not os.path.exists(file_path):
    print(f"Error: File {file_path} not found.")
    sys.exit(1)

df = pd.read_excel(file_path)

# Normalize column access
# Use 'Артикул клиента' as Request Name because 'Название клиента' is empty
df["Request"] = df["Артикул клиента"].fillna("")
df["Answer"] = df["Название поставщика"].fillna("--- NOT FOUND ---")

total = len(df)
not_found = df[df["Тип маппинга"] == "not_found"]
found = df[df["Тип маппинга"] != "not_found"]

# Stats
stats_type = df["Тип маппинга"].value_counts()

print("=== JAKKO ORDER MATCHING REPORT ===")
print(f"File: {file_path.split('/')[-1]}")
print(f"Total Items: {total}")
print(f"Matched: {len(found)} ({len(found)/total*100:.1f}%)")
print(f"Not Found: {len(not_found)} ({len(not_found)/total*100:.1f}%)")
print("\n--- Match Types ---")
print(stats_type.to_string())

if not not_found.empty:
    print("\n\n=== UNMATCHED ITEMS (Action Required) ===")
    print(f"{'Request':<60} | {'Quantity':<10}")
    print("-" * 75)
    for _, row in not_found.iterrows():
        print(f"{str(row['Request'])[:60]:<60} | {row['Количество']:<10}")

low_conf = df[df["Требует проверки"] == "Да"]
if not low_conf.empty:
    print("\n\n=== LOW CONFIDENCE MATCHES (Review Needed) ===")
    print(f"{'Request':<50} | {'Answer':<50} | {'Score':<5}")
    print("-" * 110)
    for _, row in low_conf.iterrows():
        print(
            f"{str(row['Request'])[:50]:<50} | {str(row['Answer'])[:50]:<50} | {row['Совпадение %']}"
        )

print("\n\n=== SAMPLE MATCHES (First 10) ===")
print(f"{'Request':<50} | {'Answer':<50} | {'Score':<5} | {'Type'}")
print("-" * 120)
for _, row in found.head(10).iterrows():
    print(
        f"{str(row['Request'])[:50]:<50} | {str(row['Answer'])[:50]:<50} | {row['Совпадение %']:<5} | {row['Тип маппинга']}"
    )
