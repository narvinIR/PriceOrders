import sys
import os
import argparse

# Add project root to path
sys.path.append(os.getcwd())

from backend.services.llm_matcher import LLMMatcher, get_llm_matcher


def test_relay_match(query: str):
    print(f"🧪 Testing Relay Match for: '{query}'")

    matcher = LLMMatcher()  # No key needed

    # Mock products
    products = [
        {"sku": "100-A", "name": "Труба полипропиленовая 20мм (белая)"},
        {"sku": "100-B", "name": "Муфта ППР 20мм соединительная"},
        {"sku": "200-X", "name": "Отвод 90 градусов 110мм (канализация)"},
    ]
    matcher.set_products(products)

    result = matcher.match(query)

    if result:
        print(f"✅ Match Result: {result}")
        if result["confidence"] > 50:
            print("SUCCESS: High confidence match")
        else:
            print("WARNING: Low confidence")
    else:
        print("❌ Match Failed (None returned)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", default="Труба ПП 20 бел", nargs="?")
    args = parser.parse_args()

    test_relay_match(args.query)
