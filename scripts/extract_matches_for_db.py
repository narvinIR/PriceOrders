import pandas as pd

file_path = "/home/dimas/projects/PriceOrders/jakko_order_20260124_081218.xlsx"
df = pd.read_excel(file_path)

# Filter for found items
found_df = df[df["Тип маппинга"] != "not_found"]
unique_names = found_df["Название поставщика"].dropna().unique().tolist()

print("FOUND_NAMES_START")
for name in unique_names:
    print(name)
print("FOUND_NAMES_END")
