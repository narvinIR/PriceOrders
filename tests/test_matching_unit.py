"""
Unit тесты для backend/services/matching.py
Тестирует каждый уровень matching алгоритма.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch
from uuid import UUID

sys.path.insert(0, '/home/dimas/projects/PriceOrders')

from backend.services.matching import (
    MatchingService,
    is_eco_product,
    extract_mm_from_clamp,
    clamp_fits_mm,
)


class TestIsEcoProduct:
    """Тесты для is_eco_product()"""

    def test_eco_in_name(self):
        assert is_eco_product('Труба ПП ЭКО 110×2000') is True

    def test_eko_in_name(self):
        assert is_eco_product('Труба EKO 110×2000') is True

    def test_thickness_22(self):
        assert is_eco_product('Труба ПП 110×2000 (2.2)') is True

    def test_standard_product(self):
        assert is_eco_product('Труба ПП 110×2000') is False
        assert is_eco_product('Труба ПП 110×2000 (2.7)') is False


class TestExtractMmFromClamp:
    """Тесты для extract_mm_from_clamp()"""

    def test_extract(self):
        assert extract_mm_from_clamp('хомут 110') == 110
        assert extract_mm_from_clamp('Хомут 50') == 50

    def test_no_clamp(self):
        assert extract_mm_from_clamp('Труба 110') is None


class TestClampFitsMm:
    """Тесты для clamp_fits_mm()"""

    def test_fits(self):
        assert clamp_fits_mm('Хомут в комплекте 4" (107-115)', 110) is True
        assert clamp_fits_mm('Хомут в комплекте 4" (107-115)', 107) is True
        assert clamp_fits_mm('Хомут в комплекте 4" (107-115)', 115) is True

    def test_not_fits(self):
        assert clamp_fits_mm('Хомут в комплекте 4" (107-115)', 50) is False
        assert clamp_fits_mm('Хомут в комплекте 4" (107-115)', 120) is False


class TestMatchingService:
    """Тесты для MatchingService"""

    @pytest.fixture
    def mock_matcher(self, sample_products):
        """Создаёт MatchingService с мокнутой БД"""
        with patch('backend.services.matching.get_supabase_client') as mock_db:
            mock_client = MagicMock()
            mock_db.return_value = mock_client

            # Мок для products
            mock_client.table.return_value.select.return_value.execute.return_value = \
                MagicMock(data=sample_products)

            # Мок для mappings
            mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=[])

            matcher = MatchingService()
            matcher._products_cache = sample_products
            matcher._mappings_cache = {}

            # Отключаем ML embeddings для unit тестов
            matcher._embedding_matcher._initialized = False
            yield matcher

    def test_exact_sku_match(self, mock_matcher, client_id):
        """Level 1: Точное совпадение артикула"""
        result = mock_matcher.match_item(
            client_id=client_id,
            client_sku='JK-PP-110-2000',
            client_name=''
        )
        assert result.match_type == 'exact_sku'
        assert result.confidence == 100.0
        assert result.needs_review is False

    def test_exact_name_match(self, mock_matcher, client_id):
        """Level 2: Точное совпадение названия"""
        result = mock_matcher.match_item(
            client_id=client_id,
            client_sku='UNKNOWN-SKU',
            client_name='Труба ПП канализационная 110×2000'
        )
        assert result.match_type == 'exact_name'
        assert result.confidence == 95.0
        assert result.needs_review is False

    def test_fuzzy_sku_match(self, mock_matcher, client_id):
        """Level 4: Fuzzy SKU (Levenshtein ≤ 1)"""
        result = mock_matcher.match_item(
            client_id=client_id,
            client_sku='JK-PP-110-200',  # Опечатка - 2000 → 200
            client_name=''
        )
        # Может быть fuzzy_sku или not_found
        assert result.match_type in ('fuzzy_sku', 'not_found')

    def test_fuzzy_name_match(self, mock_matcher, client_id):
        """Level 5: Fuzzy название"""
        result = mock_matcher.match_item(
            client_id=client_id,
            client_sku='UNKNOWN',
            client_name='Труба полипропилен канализационная 110×2000'
        )
        assert result.match_type in ('exact_name', 'fuzzy_name')
        assert result.confidence >= 75.0

    def test_not_found(self, mock_matcher, client_id):
        """Level 7: Не найдено"""
        result = mock_matcher.match_item(
            client_id=client_id,
            client_sku='ZZZZZZZ',
            client_name='Совершенно несуществующий товар XYZ'
        )
        assert result.match_type == 'not_found'
        assert result.confidence == 0.0
        assert result.needs_review is True


class TestSizeMatching:
    """Тесты для точного matching по размерам"""

    @pytest.fixture
    def size_matcher(self):
        """Создаёт MatchingService с тестовыми товарами разных размеров"""
        products = [
            {
                'id': '11111111-1111-1111-1111-111111111111',
                'sku': 'JK-PP-110-2000',
                'name': 'Труба ПП канализационная 110×2000',
                'category': 'Трубы',
                'pack_qty': 1
            },
            {
                'id': '22222222-2222-2222-2222-222222222222',
                'sku': 'JK-PP-110-3000',
                'name': 'Труба ПП канализационная 110×3000',
                'category': 'Трубы',
                'pack_qty': 1
            },
            {
                'id': '33333333-3333-3333-3333-333333333333',
                'sku': 'JK-PP-110-1500',
                'name': 'Труба ПП канализационная 110×1500',
                'category': 'Трубы',
                'pack_qty': 1
            },
        ]

        with patch('backend.services.matching.get_supabase_client') as mock_db:
            mock_client = MagicMock()
            mock_db.return_value = mock_client

            mock_client.table.return_value.select.return_value.execute.return_value = \
                MagicMock(data=products)
            mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=[])

            matcher = MatchingService()
            matcher._products_cache = products
            matcher._mappings_cache = {}
            matcher._embedding_matcher._initialized = False
            yield matcher

    def test_exact_size_match_2000(self, size_matcher, client_id):
        """Труба 110×2000 должна находить 110×2000, не 110×3000"""
        result = size_matcher.match_item(
            client_id=client_id,
            client_sku='',
            client_name='Труба ПП канализационная 110×2000'
        )
        assert result.product_id == UUID('11111111-1111-1111-1111-111111111111')
        assert '2000' in result.product_name

    def test_exact_size_match_3000(self, size_matcher, client_id):
        """Труба 110×3000 должна находить 110×3000"""
        result = size_matcher.match_item(
            client_id=client_id,
            client_sku='',
            client_name='Труба ПП кан. 110×3000'
        )
        assert result.product_id == UUID('22222222-2222-2222-2222-222222222222')
        assert '3000' in result.product_name

    def test_size_with_different_separator(self, size_matcher, client_id):
        """Труба 110x1500 (x вместо ×) должна находить 110×1500"""
        result = size_matcher.match_item(
            client_id=client_id,
            client_sku='',
            client_name='Труба ПП кан. 110x1500'
        )
        assert result.product_id == UUID('33333333-3333-3333-3333-333333333333')
        assert '1500' in result.product_name


class TestEcoPreference:
    """Тесты для предпочтения стандарта vs ЭКО"""

    @pytest.fixture
    def eco_matcher(self):
        """Создаёт matcher с товарами стандарт и ЭКО"""
        products = [
            {
                'id': '11111111-1111-1111-1111-111111111111',
                'sku': 'JK-PP-110-2000',
                'name': 'Труба ПП 110×2000 (2.7)',
                'category': 'Трубы',
                'pack_qty': 1
            },
            {
                'id': '22222222-2222-2222-2222-222222222222',
                'sku': 'JK-PP-110-2000-ECO',
                'name': 'Труба ПП ЭКО 110×2000 (2.2)',
                'category': 'Трубы',
                'pack_qty': 1
            },
        ]

        with patch('backend.services.matching.get_supabase_client') as mock_db:
            mock_client = MagicMock()
            mock_db.return_value = mock_client

            mock_client.table.return_value.select.return_value.execute.return_value = \
                MagicMock(data=products)
            mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=[])

            matcher = MatchingService()
            matcher._products_cache = products
            matcher._mappings_cache = {}
            matcher._embedding_matcher._initialized = False
            yield matcher

    def test_prefer_standard_when_no_eco_specified(self, eco_matcher, client_id):
        """Без указания ЭКО - предпочитаем стандарт"""
        result = eco_matcher.match_item(
            client_id=client_id,
            client_sku='',
            client_name='Труба ПП 110×2000'
        )
        assert 'ЭКО' not in result.product_name
        assert '2.7' in result.product_name

    def test_find_eco_when_specified(self, eco_matcher, client_id):
        """При указании ЭКО - находим ЭКО"""
        result = eco_matcher.match_item(
            client_id=client_id,
            client_sku='',
            client_name='Труба ПП ЭКО 110×2000'
        )
        assert 'ЭКО' in result.product_name
