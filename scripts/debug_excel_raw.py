import pandas as pd

file_path = "/home/dimas/projects/PriceOrders/jakko_order_20260124_081218.xlsx"
# Read without header to see raw data
df = pd.read_excel(file_path, header=None, nrows=10)
print(df.to_string())
