"""
Тест предпочтения категорий при matching.
По умолчанию без указания материала - канализационные (серые).
"""
import sys
sys.path.insert(0, '/home/dimas/projects/PriceOrders')

from backend.services.matching import MatchingService, detect_client_category


def test_detect_client_category():
    """Тест определения категории из запроса"""
    # Prestige - белая/малошумная канализация
    assert detect_client_category("труба белая кан 110") == 'prestige'
    assert detect_client_category("отвод малошумный 50") == 'prestige'
    assert detect_client_category("заглушка prestige 110") == 'prestige'

    # Наружная канализация - рыжая
    assert detect_client_category("труба нар.кан 110") == 'outdoor'
    assert detect_client_category("отвод наружный 160") == 'outdoor'
    assert detect_client_category("труба рыжая 110") == 'outdoor'

    # ППР - водопровод/отопление (белый, но НЕ канализация)
    assert detect_client_category("отвод ппр 50") == 'ppr'
    assert detect_client_category("труба PPR 20") == 'ppr'
    assert detect_client_category("муфта белая 32") == 'ppr'  # белая без "кан" = ППР

    # Обычная серая канализация
    assert detect_client_category("труба кан 110") == 'sewer'
    assert detect_client_category("отвод канализационный 50") == 'sewer'
    assert detect_client_category("заглушка серая 110") == 'sewer'

    # Не указано - дефолт будет серая кан.
    assert detect_client_category("отвод 50 45") is None
    assert detect_client_category("заглушка 110") is None
    assert detect_client_category("переходник 50-32") is None


def test_prefer_sewer_by_default():
    """Без указания материала - предпочитать канализационные"""
    matcher = MatchingService()

    cases = [
        "отвод 50 45",
        "заглушка 110",
        "переходник 50-32",
    ]

    for query in cases:
        result = matcher.match_item(None, query, query)
        # Проверяем что выбран канализационный товар
        is_sewer = (
            'кан' in result.product_name.lower() or
            result.product_sku.startswith('202') or  # Трубы кан. ПП
            result.product_sku.startswith('303') or  # Наружная кан.
            result.product_sku.startswith('403')     # Малошумные
        )
        assert is_sewer, (
            f"Query '{query}': expected sewer product, got PPR: "
            f"{result.product_sku} ({result.product_name})"
        )
        print(f"✅ '{query}' → {result.product_sku} {result.product_name}")


def test_prefer_ppr_when_specified():
    """Если указан ППР - выбирать ППР"""
    matcher = MatchingService()

    cases = [
        ("отвод ппр 50 45", "ППР"),
        ("заглушка ппр 110", "ППР"),
    ]

    for query, expected_in_name in cases:
        result = matcher.match_item(None, query, query)
        assert expected_in_name in result.product_name, (
            f"Query '{query}': expected '{expected_in_name}' in name, "
            f"got {result.product_name}"
        )
        print(f"✅ '{query}' → {result.product_sku} {result.product_name}")


if __name__ == '__main__':
    print("=" * 60)
    print("ТЕСТ ОПРЕДЕЛЕНИЯ КАТЕГОРИИ")
    print("=" * 60)
    test_detect_client_category()
    print("✅ detect_client_category работает корректно\n")

    print("=" * 60)
    print("ТЕСТ: БЕЗ УКАЗАНИЯ МАТЕРИАЛА → КАНАЛИЗАЦИЯ")
    print("=" * 60)
    test_prefer_sewer_by_default()
    print()

    print("=" * 60)
    print("ТЕСТ: С УКАЗАНИЕМ ППР → ППР")
    print("=" * 60)
    test_prefer_ppr_when_specified()
    print()

    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
