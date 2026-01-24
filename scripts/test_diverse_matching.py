#!/usr/bin/env python3
"""
Comprehensive test with diverse product categories.
Tests all 839 products' categories, not just pipes.

Usage:
    PYTHONPATH=. python3 scripts/test_diverse_matching.py
"""

import sys

sys.path.insert(0, ".")

from backend.services.matching import MatchingService

# Diverse test cases across ALL categories
TEST_CASES = [
    # === ППР фитинги (polypropylene) ===
    ("Муфта ПП 32", "Муфта ППР"),
    ("Труба ППР 25 PN20", "Труба ППР"),
    ("Тройник ПП 40", "Тройник ППР"),
    ("Угольник ППР 25", "Отвод ППР"),
    ("Кран шаровой 25", "Кран"),
    ("Американка 32", "Муфта разъемная"),
    # === Компрессионные фитинги ===
    ("Муфта компрессионная 32", "компрес"),
    ("Отвод компресс 25", "компрес"),
    ("Тройник компресс 32x1/2", "компрес"),
    # === Канализация серая ===
    ("Труба кан 110", "кан"),
    ("Ревизия 110", "Ревизия"),
    ("Крестовина 110", "Крестовина"),
    ("Заглушка кан 50", "Заглушка"),
    # === Наружная канализация ===
    ("Труба нар 160", "нар"),
    ("Муфта нар.кан. 110", "нар"),
    # === Рифленые трубы (дренаж) ===
    ("Труба рифленая 110", "рифлен"),
    ("Переходник рифленый 160", "рифлен"),
    # === Хомуты и крепёж ===
    ("Хомут 1/2", "Хомут"),
    ("Клипсы 20", "Клипс"),
    # === Edge cases ===
    ("Муфта НР 32*1", "резьб"),  # С резьбой
    ("Тройник ред 40-25-40", "переходник"),  # Редукционный
    ("Штуцер 25", "Штуцер"),
    ("Фильтр 32", "Фильтр"),
    ("Компенсатор 40", "Компенсатор"),
]


def run_tests():
    print("🧪 Diverse Matching Test Suite (All Categories)")
    print("=" * 70)
    print()

    service = MatchingService()

    passed = 0
    failed = 0

    for query, expected_substr in TEST_CASES:
        result = service.match_item(None, "", query)

        if not result or not result.product_id:
            print(f"❌ '{query}' → NO MATCH")
            failed += 1
            continue

        name = result.product_name or ""
        confidence = result.confidence or 0
        match_type = result.match_type or "?"

        # Check if expected substring is in result
        found = expected_substr.lower() in name.lower()

        status = "✅" if found else "⚠️"
        if found:
            passed += 1
        else:
            failed += 1

        print(f"{status} '{query}'")
        print(f"   → {name} ({confidence:.0f}%, {match_type})")
        if not found:
            print(f"   ⚠️ Expected '{expected_substr}' in name")
        print()

    print("=" * 70)
    print(f"📊 Results: ✅ {passed} passed, ❌ {failed} failed")
    print(f"   Total: {len(TEST_CASES)} tests")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
