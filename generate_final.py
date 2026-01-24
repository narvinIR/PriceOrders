import sys
import os
from unittest.mock import MagicMock

# Mock OpenAI dependencies
sys.modules["openai"] = MagicMock()
sys.modules["backend.utils.openai_client"] = MagicMock()
embeddings_mock = MagicMock()
dummy_matcher = MagicMock()
dummy_matcher.is_ready = False
dummy_matcher.build_index = MagicMock()
embeddings_mock.get_embedding_matcher.return_value = dummy_matcher
sys.modules["backend.services.embeddings"] = embeddings_mock

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, "/home/dimas/projects/PriceOrders")
load_dotenv()

# Reload modules to be safe
import importlib

if "backend.services.matching" in sys.modules:
    import backend.services.matching

    importlib.reload(backend.services.matching)

from backend.services.matching import MatchingService


def generate_report():
    print("Initializing Matcher...")
    try:
        matcher = MatchingService()
    except Exception as e:
        print(f"Error: {e}")
        return

    raw_items = """Заглушка компрессионная 25 Tebo/UNIO 30
Заглушка компрессионная 40 Tebo/UNIO 30
Заглушка компрессионная 63 Tebo 10
Кран шаровой 20 x 1/2" нар. резьба компрессионный Tebo/UNIO 60
Кран шаровой 20 компрессионный Tebo/UNIO 100
Кран шаровой 25 x 3/4" нар. резьба компрессионный Tebo/UNIO 50
Кран шаровой 25 компрессионный Tebo/UNIO 150
Кран шаровой 32 компрессионный Tebo/UNIO 100
Муфта компрессионная 20 Tebo/UNIO 60
Муфта компрессионная 25 Tebo/UNIO 255
Муфта компрессионная 32 Tebo/UNIO 50
Муфта компрессионная 40 Tebo/UNIO 24
Муфта компрессионная 50 Tebo/UNIO 54
Муфта компрессионная ВР 25х3/4'' Tebo/UNIO 150
Муфта компрессионная ВР 32х1'' Tebo/UNIO 100
Муфта компрессионная ВР 40х1 1/4'' Tebo/UNIO 50
Муфта компрессионная ВР 40х1'' Tebo/UNIO 20
Муфта компрессионная ВР 63х2'' Tebo 20
Муфта компрессионная НР 20х1/2'' Tebo/UNIO 100
Муфта компрессионная НР 25х1'' Tebo/UNIO 120
Муфта компрессионная НР 25х1/2'' Tebo/UNIO 300
Муфта компрессионная НР 25х3/4'' Tebo/UNIO 125
Муфта компрессионная НР 32х1'' Tebo/UNIO 200
Муфта компрессионная НР 32х1/2'' Tebo/UNIO 30
Муфта компрессионная НР 32х3/4'' Tebo/UNIO 120
Муфта компрессионная НР 40х1 1/2'' Tebo 10
Муфта компрессионная НР 40х1'' Tebo/UNIO 20
Муфта компрессионная НР 50х1 1/2'' Tebo/UNIO 10
Муфта компрессионная НР 50х1 1/4'' Tebo/UNIO 20
Муфта компрессионная редукционная 25*20 Tebo/UNIO 40
Муфта компрессионная редукционная 32*20 Tebo/UNIO 20
Муфта компрессионная редукционная 32*25 Tebo/UNIO 30
Муфта компрессионная редукционная 40*32 Tebo 24
Отвод компрессионный 20 Tebo/UNIO 200
Отвод компрессионный 25 Tebo/UNIO 300
Отвод компрессионный 32 Tebo/UNIO 104
Отвод компрессионный 50 Tebo/UNIO 50
Отвод компрессионный 63 Tebo/UNIO 20
Отвод компрессионный ВР 25*3/4" Tebo/UNIO 15
Отвод компрессионный НР 25*1" Tebo 20
Тройник компрессионный 20 Tebo/UNIO 150
Тройник компрессионный НР 25х1/2'' Tebo/UNIO 50
Тройник редукционный 25*20*25 Tebo/UNIO 10"""

    data = []
    lines = raw_items.strip().split("\n")
    for line in lines:
        parts = line.rsplit(" ", 1)
        name = parts[0].strip()
        qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

        result = matcher.match_item(client_id=None, client_sku=name, client_name=name)

        # Determine strict status
        # If product_sku equals client_name (based on my mock fallback), it's Not Found?
        # My matcher returns MatchResult.
        # If not found, MatchResult(product_id=None, match_type='not_found')

        sku = result.product_sku
        jakko_name = result.product_name

        if not result.product_id:
            match_status = "not_found"
            sku = None
            jakko_name = None
        else:
            match_status = result.match_type

        row = {
            "Запрос": name,
            "Кол-во": qty,
            "Артикул": sku,
            "Наименование Jakko": jakko_name,
            "Метод": match_status,
            "Confidence": round(result.confidence, 1),
        }
        data.append(row)

    df = pd.DataFrame(data)

    # Sort: Found first, then Not Found
    df["found"] = df["Артикул"].notna()
    df = df.sort_values(by=["found", "Запрос"], ascending=[False, True])
    df = df.drop(columns=["found"])

    outfile = "zakaz_jakko_FINAL.xlsx"
    df.to_excel(outfile, index=False)
    print(f"Saved to {outfile}")


if __name__ == "__main__":
    generate_report()
