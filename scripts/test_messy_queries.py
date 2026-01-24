import asyncio
import logging
import os
from backend.services.llm_matcher import get_llm_matcher

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Mock Catalog (Типичные товары Jakko)
MOCK_PRODUCTS = [
    {"sku": "11001", "name": "Труба стекловолокно PN20 20 мм (белая)"},
    {"sku": "11002", "name": "Труба стекловолокно PN20 25 мм (белая)"},
    {"sku": "12001", "name": "Муфта соединительная 20 мм"},
    {"sku": "12002", "name": "Отвод 90 градусов 20 мм"},
    {"sku": "12003", "name": "Отвод 45 градусов 20 мм"},
    {"sku": "13001", "name": "Муфта комбинированная НР 20х1/2 (наружная резьба)"},
    {"sku": "13002", "name": "Муфта комбинированная ВР 20х1/2 (внутренняя резьба)"},
    {"sku": "14001", "name": "Тройник 20 мм"},
    {"sku": "14002", "name": "Тройник переходной 25х20х25 мм"},
]

# 2. Messy Queries (Ошибки, сленг, сокращения)
TEST_QUERIES = [
    # Запрос -> Ожидаемый SKU (для проверки глазами)
    ("труба 20 стекло", "11001"),  # Сокращение
    ("угол 20", "12002"),  # Синоним (Угол = Отвод 90)
    ("колено 20 45гр", "12003"),  # Синоним (Колено = Отвод) + градус
    ("муфта 20*1/2 наружняя", "13001"),  # Опечатка (наружняя) + формат размера
    ("тройгик 20", "14001"),  # Жесткая опечатка
    ("перходник 25 на 20", "14002"),  # Описание функции (тройник переходной)
]


def run_tests():
    matcher = get_llm_matcher()
    matcher.set_products(MOCK_PRODUCTS)

    print(f"\n🧪 TESTING MESSY QUERIES ({len(TEST_QUERIES)} items)...\n")
    print(
        f"{'QUERY':<30} | {'EXPECTED':<10} | {'ACTUAL SKU':<10} | {'NAME':<40} | {'CONF'}"
    )
    print("-" * 110)

    for query, expected_sku in TEST_QUERIES:
        # Note: Match is synchronous thanks to our bridge
        result = matcher.match(query)

        actual_sku = result.get("sku") if result else "NONE"
        actual_name = result.get("name") if result else "---"
        confidence = result.get("confidence", 0)

        status = "✅" if actual_sku == expected_sku else "❌"

        # Shorten name
        if len(actual_name) > 38:
            actual_name = actual_name[:35] + "..."

        print(
            f"{query:<30} | {expected_sku:<10} | {actual_sku:<10} | {actual_name:<40} | {confidence}% {status}"
        )


if __name__ == "__main__":
    run_tests()
