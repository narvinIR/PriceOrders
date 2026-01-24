import sys
import os
from unittest.mock import MagicMock

# Mock OpenAI dependencies BEFORE importing anything else
sys.modules["openai"] = MagicMock()
sys.modules["backend.utils.openai_client"] = MagicMock()

# Creating a mock for backend.services.embeddings
embeddings_mock = MagicMock()
# Setup get_embedding_matcher to return a dummy matcher
dummy_matcher = MagicMock()
dummy_matcher.is_ready = True  # Pretend it's ready or False to skip?
# specific logic: if is_ready is False, it calls build_index.
# Let's say False, and build_index does nothing.
dummy_matcher.is_ready = False
dummy_matcher.build_index = MagicMock()
embeddings_mock.get_embedding_matcher.return_value = dummy_matcher

sys.modules["backend.services.embeddings"] = embeddings_mock

sys.path.insert(0, "/home/dimas/projects/PriceOrders")

# Load env vars
from dotenv import load_dotenv

load_dotenv()

# Force reload modules
import importlib
import backend.utils.normalizers as n
import backend.services.matching_strategies.hybrid as h

# Note: we don't reload matching yet as it wasn't imported
# But if it was cached in sys.modules, we should reload it.
if "backend.services.matching" in sys.modules:
    import backend.services.matching

    importlib.reload(backend.services.matching)

import backend.services.matching as m

importlib.reload(h)
importlib.reload(m)

from backend.services.matching import MatchingService


def run_test():
    print("Initializing Matcher...")
    try:
        matcher = MatchingService()
    except Exception as e:
        print(f"Error initializing MatchingService: {e}")
        # Debug why
        import traceback

        traceback.print_exc()
        return

    # Raw list from client
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

    expected = {
        "Муфта компрессионная ВР 25х3/4": "704024251T",
        "Муфта компрессионная ВР 32х1": "704027321T",
        "Муфта компрессионная НР 20х1/2": "704034502T",
        "Муфта компрессионная НР 25х1": "704036252T",
        "Муфта компрессионная НР 25х1/2": "704037254T",
        "Муфта компрессионная НР 25х3/4": "704038251T",
        "Муфта компрессионная НР 32х1": "704042325T",
        "Муфта компрессионная НР 32х1/2": "704041321T",
        "Муфта компрессионная НР 32х3/4": "704042324T",
    }

    correct_count = 0
    total_count = 0

    print("\n=== MATCHING RESULTS ===")
    lines = raw_items.strip().split("\n")
    for line in lines:
        parts = line.rsplit(" ", 1)
        name = parts[0].strip()

        result = matcher.match_item(client_id=None, client_sku=name, client_name=name)
        sku = result.product_sku if result else None

        # Check against expected critical items
        status = " "
        exp_sku = None
        # Sort keys by length descending to match longest key first (e.g. match '25x1/2' before '25x1')
        sorted_keys = sorted(expected.keys(), key=len, reverse=True)
        for k in sorted_keys:
            if k in name:
                exp_sku = expected[k]
                break

        if exp_sku:
            if sku == exp_sku:
                status = "✅"
                correct_count += 1
            else:
                status = f"❌ (Exp: {exp_sku})"
            total_count += 1
        elif sku:
            # Check if it erroneously matched expected sku of another item? No.
            status = "ok"
        else:
            status = "❓"

        # Shorten name for display
        short_name = (name[:45] + "..") if len(name) > 45 else name
        print(f"{status} {short_name:47} -> {sku}")

    print(f"\nCritical Accuracy: {correct_count}/{total_count}")


if __name__ == "__main__":
    run_test()
