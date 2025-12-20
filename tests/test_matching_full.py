"""
Полный тест matching на реальных данных из БД.
Создаёт тестовые вариации названий товаров и проверяет matching.
"""
import sys
sys.path.insert(0, '/home/dimas/projects/PriceOrders')

from uuid import UUID
from backend.services.matching import MatchingService
from backend.models.database import get_supabase_client

# Тестовый client_id
TEST_CLIENT_ID = UUID('00000000-0000-0000-0000-000000000001')


def create_client_variations(product: dict) -> list[dict]:
    """
    Создаёт вариации названия товара, как мог бы написать клиент.
    Возвращает список {client_name, client_sku, expected_id}
    """
    name = product['name']
    sku = product['sku']
    product_id = product['id']

    variations = []

    # Вариация 1: точное название
    variations.append({
        'client_name': name,
        'client_sku': sku,
        'expected_id': product_id,
        'variation': 'exact'
    })

    # Вариация 2: только SKU
    variations.append({
        'client_name': '',
        'client_sku': sku,
        'expected_id': product_id,
        'variation': 'sku_only'
    })

    # Вариация 3: название без бренда (Jk, Jakko)
    name_no_brand = name.replace('Jk ', '').replace('Jakko ', '')
    if name_no_brand != name:
        variations.append({
            'client_name': name_no_brand,
            'client_sku': '',
            'expected_id': product_id,
            'variation': 'no_brand'
        })

    # Вариация 4: сокращения материалов
    name_abbr = name
    replacements = [
        ('полипропилен', 'ПП'),
        ('Полипропилен', 'ПП'),
        ('полиэтилен', 'ПЭ'),
        ('Полиэтилен', 'ПЭ'),
        ('канализационная', 'кан.'),
        ('канализационный', 'кан.'),
    ]
    for full, abbr in replacements:
        name_abbr = name_abbr.replace(full, abbr)
    if name_abbr != name:
        variations.append({
            'client_name': name_abbr,
            'client_sku': '',
            'expected_id': product_id,
            'variation': 'abbreviated'
        })

    # Вариация 5: изменённый размер (x вместо ×)
    if '×' in name:
        name_x = name.replace('×', 'x')
        variations.append({
            'client_name': name_x,
            'client_sku': '',
            'expected_id': product_id,
            'variation': 'x_separator'
        })

    # Вариация 6: для резьбы - сокращения
    if 'внутренняя резьба' in name.lower():
        name_abbr = name.lower().replace('внутренняя резьба', 'вн.рез.')
        variations.append({
            'client_name': name_abbr,
            'client_sku': '',
            'expected_id': product_id,
            'variation': 'thread_abbr'
        })
    if 'наружная резьба' in name.lower():
        name_abbr = name.lower().replace('наружная резьба', 'нар.рез.')
        variations.append({
            'client_name': name_abbr,
            'client_sku': '',
            'expected_id': product_id,
            'variation': 'thread_abbr'
        })

    # Вариация 7: для труб PN - разные форматы
    if 'PN' in name:
        import re
        # PN20 → PN 20
        name_pn = re.sub(r'PN(\d+)', r'PN \1', name)
        if name_pn != name:
            variations.append({
                'client_name': name_pn,
                'client_sku': '',
                'expected_id': product_id,
                'variation': 'pn_space'
            })

    # Вариация 8: малошумная → малошум.
    if 'малошумная' in name.lower():
        name_abbr = name.lower().replace('малошумная', 'малошум.')
        variations.append({
            'client_name': name_abbr,
            'client_sku': '',
            'expected_id': product_id,
            'variation': 'quiet_abbr'
        })

    # Вариация 9: угол/колено вместо отвод
    if 'отвод' in name.lower():
        name_alt = name.lower().replace('отвод', 'угол')
        variations.append({
            'client_name': name_alt,
            'client_sku': '',
            'expected_id': product_id,
            'variation': 'elbow_synonym'
        })

    return variations


def run_test():
    """Запуск полного теста"""
    db = get_supabase_client()
    matcher = MatchingService()

    # Получаем все товары
    response = db.table('products').select('*').execute()
    products = response.data or []

    print(f"📦 Загружено товаров: {len(products)}")
    print("=" * 80)

    # Статистика по категориям
    categories = {}
    for p in products:
        cat = p.get('category', 'Unknown')
        categories[cat] = categories.get(cat, 0) + 1

    print("\n📊 Товаров по категориям:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {count}")

    # Генерируем тестовые кейсы (берём по 10 товаров из каждой категории)
    test_cases = []
    samples_per_category = 10

    for cat in categories:
        cat_products = [p for p in products if p.get('category') == cat][:samples_per_category]
        for product in cat_products:
            variations = create_client_variations(product)
            test_cases.extend(variations)

    print(f"\n🧪 Сгенерировано тестов: {len(test_cases)}")
    print("=" * 80)

    # Прогоняем тесты
    results = {
        'passed': [],
        'failed': [],
        'not_found': []
    }

    for i, tc in enumerate(test_cases):
        match = matcher.match_item(
            client_id=TEST_CLIENT_ID,
            client_sku=tc['client_sku'],
            client_name=tc['client_name']
        )

        expected_id = tc['expected_id']
        matched_id = str(match.product_id) if match.product_id else None

        if matched_id == expected_id:
            results['passed'].append({
                **tc,
                'match': match,
                'confidence': match.confidence,
                'match_type': match.match_type
            })
        elif match.product_id is None:
            results['not_found'].append({
                **tc,
                'match': match
            })
        else:
            results['failed'].append({
                **tc,
                'match': match,
                'matched_name': match.product_name
            })

        # Прогресс
        if (i + 1) % 50 == 0:
            print(f"   Обработано: {i + 1}/{len(test_cases)}")

    # Выводим результаты
    total = len(test_cases)
    passed = len(results['passed'])
    failed = len(results['failed'])
    not_found = len(results['not_found'])

    print("\n" + "=" * 80)
    print("📈 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    print(f"✅ Успешно: {passed}/{total} ({100*passed/total:.1f}%)")
    print(f"❌ Ошибочно: {failed}/{total} ({100*failed/total:.1f}%)")
    print(f"❓ Не найдено: {not_found}/{total} ({100*not_found/total:.1f}%)")

    # Детали ошибок
    if results['failed']:
        print("\n" + "=" * 80)
        print("❌ ОШИБКИ MATCHING (найден не тот товар):")
        print("=" * 80)
        for r in results['failed'][:20]:  # Первые 20
            print(f"\n🔍 Запрос: {r['client_name'] or r['client_sku']}")
            print(f"   Вариация: {r['variation']}")
            print(f"   Ожидался: {r['expected_id'][:8]}...")
            print(f"   Найден:   {r['match'].product_id}")
            print(f"   Название: {r['matched_name']}")
            print(f"   Confidence: {r['match'].confidence:.1f}%")

    if results['not_found']:
        print("\n" + "=" * 80)
        print("❓ НЕ НАЙДЕНО:")
        print("=" * 80)
        for r in results['not_found'][:20]:  # Первые 20
            print(f"\n🔍 Запрос: {r['client_name'] or r['client_sku']}")
            print(f"   Вариация: {r['variation']}")
            print(f"   Ожидался: {r['expected_id'][:8]}...")

    # Статистика по типам match
    print("\n" + "=" * 80)
    print("📊 СТАТИСТИКА ПО ТИПАМ MATCH:")
    print("=" * 80)
    match_types = {}
    for r in results['passed']:
        mt = r['match_type']
        match_types[mt] = match_types.get(mt, 0) + 1

    for mt, count in sorted(match_types.items(), key=lambda x: -x[1]):
        print(f"   {mt}: {count} ({100*count/passed:.1f}%)")

    # Статистика по вариациям
    print("\n" + "=" * 80)
    print("📊 УСПЕШНОСТЬ ПО ВАРИАЦИЯМ:")
    print("=" * 80)

    variation_stats = {}
    for tc in test_cases:
        var = tc['variation']
        if var not in variation_stats:
            variation_stats[var] = {'total': 0, 'passed': 0}
        variation_stats[var]['total'] += 1

    for r in results['passed']:
        var = r['variation']
        variation_stats[var]['passed'] += 1

    for var, stats in sorted(variation_stats.items(), key=lambda x: x[1]['passed']/x[1]['total'] if x[1]['total'] > 0 else 0):
        pct = 100 * stats['passed'] / stats['total'] if stats['total'] > 0 else 0
        status = "✅" if pct >= 90 else "⚠️" if pct >= 70 else "❌"
        print(f"   {status} {var}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")

    return results


if __name__ == '__main__':
    run_test()
