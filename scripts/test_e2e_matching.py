"""
End-to-end test for MatchingService with ML vector search.
Verifies that category/color logic works correctly.
"""

import os
import sys

sys.path.insert(0, "/home/dimas/projects/PriceOrders")

from dotenv import load_dotenv

load_dotenv()

from backend.services.matching import MatchingService


def test_matching():
    print("🧪 E2E Matching Test")
    print("=" * 60)

    service = MatchingService()

    # Test cases: (client_name, expected_category, expected_in_result)
    test_cases = [
        # Без указания цвета → серая канализация (категория sewer)
        ("Ревизия кан. 110", "серый", "sewer"),
        ("Тройник кан. 110", "серый", "sewer"),
        # Белая/Prestige → малошумная канализация
        ("Ревизия кан. 110 белая", "Prestige", "prestige"),
        ("Тройник кан. 110 малошумный", "Prestige", "prestige"),
        # ППР (полипропилен)
        ("Муфта ПП 32", "ппр", "ppr"),
        # Наружная канализация (оранжевая/рыжая)
        ("Труба нар.кан. 110", "наружн", "outdoor"),
    ]

    for client_name, expected_marker, category in test_cases:
        print(f"\n📋 Запрос: '{client_name}'")
        print(f"   Ожидаемая категория: {category}")

        result = service.match_item(
            client_id=None, client_sku="TEST", client_name=client_name
        )

        if result.product_name:
            name_lower = result.product_name.lower()
            marker_found = expected_marker.lower() in name_lower

            status = "✅" if marker_found else "⚠️"
            print(f"   {status} Результат: {result.product_name}")
            print(f"      SKU: {result.product_sku}")
            print(f"      Confidence: {result.confidence:.1f}%")
            print(f"      Match type: {result.match_type}")

            if not marker_found:
                print(f"      ⚠️ Ожидался маркер '{expected_marker}' в названии!")
        else:
            print(f"   ❌ Не найдено совпадение")

    print("\n" + "=" * 60)
    print("✅ Тест завершен")


if __name__ == "__main__":
    test_matching()
