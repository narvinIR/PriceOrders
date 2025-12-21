"""
Тест matching для бота - эмулирует обработку текстового списка артикулов.
"""
import sys
sys.path.insert(0, '/home/dimas/projects/PriceOrders')

from backend.services.matching import MatchingService
from backend.models.schemas import MatchResult


def test_bot_matching():
    """Тест как работает matching из бота"""

    # Тестовые данные (как от клиента)
    test_items = [
        {'sku': 'Труба кан ПП 32-500', 'name': '', 'qty': 10},
        {'sku': 'Труба ПП 40-1000', 'name': '', 'qty': 5},
        {'sku': 'Труба 50-1500 эко', 'name': '', 'qty': 3},
        {'sku': 'муфта 32', 'name': '', 'qty': 1},
        {'sku': 'отвод 50 45', 'name': '', 'qty': 1},
        {'sku': 'труба пэ 32 25м', 'name': '', 'qty': 1},
        {'sku': 'хомут 110', 'name': '', 'qty': 1},
        {'sku': 'переходник 50-32', 'name': '', 'qty': 1},
        {'sku': 'заглушка 110', 'name': '', 'qty': 1},
        {'sku': '704001232R', 'name': '', 'qty': 1},
    ]

    print("=" * 80)
    print("ТЕСТ MATCHING ДЛЯ БОТА")
    print("=" * 80)

    matcher = MatchingService()
    client_id = None  # Как в боте

    results = []
    matched = 0
    not_found = 0
    errors = []

    for item in test_items:
        client_sku = item.get('sku', '')
        client_name = item.get('name', '')
        qty = item.get('qty', 1)

        print(f"\n🔍 Запрос: {client_sku!r}")

        try:
            result = matcher.match_item(
                client_id=client_id,
                client_sku=client_sku,
                client_name=client_name or client_sku
            )

            # Проверяем наличие pack_qty
            try:
                pack_qty = result.pack_qty
                print(f"   pack_qty: {pack_qty}")
            except AttributeError as e:
                errors.append(f"pack_qty missing: {e}")
                pack_qty = 1

            if result.product_sku:
                # Расчёт количества с упаковкой
                if pack_qty > 1 and qty > 0:
                    packs_needed = (qty + pack_qty - 1) // pack_qty
                    total_qty = packs_needed * pack_qty
                else:
                    total_qty = qty

                print(f"   ✅ Найден: {result.product_sku} - {result.product_name}")
                print(f"   Confidence: {result.confidence:.1f}% ({result.match_type})")
                print(f"   Количество: {qty} → {total_qty} шт (pack_qty={pack_qty})")

                results.append({
                    'input': client_sku,
                    'sku': result.product_sku,
                    'name': result.product_name,
                    'qty': total_qty,
                    'confidence': result.confidence,
                    'match_type': result.match_type,
                    'pack_qty': pack_qty
                })
                matched += 1
            else:
                print(f"   ❌ Не найден")
                results.append({
                    'input': client_sku,
                    'sku': None,
                    'name': None,
                    'qty': qty,
                    'confidence': 0,
                    'match_type': 'not_found',
                    'pack_qty': 1
                })
                not_found += 1

        except Exception as e:
            print(f"   💥 ОШИБКА: {e}")
            errors.append(f"{client_sku}: {e}")

    # Итоги
    print("\n" + "=" * 80)
    print("ИТОГИ")
    print("=" * 80)
    print(f"Найдено: {matched}/{len(test_items)}")
    print(f"Не найдено: {not_found}/{len(test_items)}")

    if errors:
        print(f"\n❌ ОШИБКИ ({len(errors)}):")
        for err in errors:
            print(f"   • {err}")
    else:
        print("\n✅ Ошибок нет!")

    # Формируем вывод как в боте
    print("\n" + "=" * 80)
    print("ВЫВОД БОТА (эмуляция)")
    print("=" * 80)

    result_lines = []
    for r in results:
        if r['sku']:
            line = f"{r['sku']} {r['name']} — {r['qty']} шт"
            result_lines.append(line)
        else:
            line = f"❌ {r['input']} — не найдено"
            result_lines.append(line)

    for line in result_lines:
        print(line)

    return len(errors) == 0


if __name__ == '__main__':
    success = test_bot_matching()
    sys.exit(0 if success else 1)
