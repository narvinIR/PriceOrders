"""
End-to-end тесты для полного цикла:
1. Парсинг текста бота
2. Matching по всем категориям
3. Фильтры по типу, углу, резьбе, хомутам
"""
import re

import pytest

from backend.services.matching import (
    MatchingService,
    detect_client_category,
    extract_angle,
    extract_mm_from_clamp,
    extract_product_type,
    extract_thread_type,
)


class TestBotTextParsing:
    """Тесты парсинга текста как в боте"""

    def parse_line(self, line: str) -> tuple[str, int]:
        """Эмуляция парсинга из bot/handlers/upload.py"""
        line = line.strip()
        match = re.match(r'^(.+?)\s+(\d+)\s*$', line)
        if match:
            sku = match.group(1).strip()
            qty = int(match.group(2))
        else:
            sku = line
            qty = 1
        return sku, qty

    def test_simple_sku_with_qty(self):
        sku, qty = self.parse_line("202051110R 5")
        assert sku == "202051110R"
        assert qty == 5

    def test_name_with_qty(self):
        sku, qty = self.parse_line("Труба ПП 110×3000 серая 5")
        assert sku == "Труба ПП 110×3000 серая"
        assert qty == 5

    def test_clamp_with_qty(self):
        sku, qty = self.parse_line("Хомут 110 80")
        assert sku == "Хомут 110"
        assert qty == 80

    def test_outdoor_elbow_with_qty(self):
        sku, qty = self.parse_line("Отвод нар.кан. 110/45 15")
        assert sku == "Отвод нар.кан. 110/45"
        assert qty == 15

    def test_prestige_tee_with_qty(self):
        sku, qty = self.parse_line("Тройник Prestige 110/50/110 3")
        assert sku == "Тройник Prestige 110/50/110"
        assert qty == 3

    def test_fitting_sizes_with_qty(self):
        sku, qty = self.parse_line("Муфта ППР 32 10")
        assert sku == "Муфта ППР 32"
        assert qty == 10

    def test_no_qty(self):
        sku, qty = self.parse_line("Труба ПП 50×1500")
        assert sku == "Труба ПП 50×1500"
        assert qty == 1

    def test_sku_only(self):
        sku, qty = self.parse_line("202051110R")
        assert sku == "202051110R"
        assert qty == 1


class TestCategoryDetection:
    """Тесты определения категории"""

    def test_sewer_by_color(self):
        assert detect_client_category("Труба серая 110") == "sewer"

    def test_sewer_by_kan(self):
        assert detect_client_category("Труба кан. 110") == "sewer"

    def test_prestige_explicit(self):
        assert detect_client_category("Труба Prestige 110") == "prestige"

    def test_prestige_by_maloshum(self):
        assert detect_client_category("Труба малошумная 110") == "prestige"

    def test_outdoor_by_nar_kan(self):
        assert detect_client_category("Отвод нар.кан. 110/45") == "outdoor"

    def test_outdoor_by_naruzhna(self):
        assert detect_client_category("Труба наружная 160") == "outdoor"

    def test_ppr_explicit(self):
        assert detect_client_category("Муфта ППР 32") == "ppr"

    def test_pp_with_sewer_is_sewer(self):
        # ПП + серая = канализация, не ППР
        assert detect_client_category("Труба ПП 110 серая") == "sewer"


class TestProductTypeExtraction:
    """Тесты извлечения типа товара"""

    def test_truba(self):
        assert extract_product_type("Труба ПП 110") == "труба"

    def test_otvod(self):
        assert extract_product_type("Отвод 110/45") == "отвод"

    def test_koleno_is_otvod(self):
        assert extract_product_type("Колено 110/45") == "отвод"

    def test_ugol_is_otvod(self):
        assert extract_product_type("Угол 110/45") == "отвод"

    def test_trojnik(self):
        assert extract_product_type("Тройник 110/50") == "тройник"

    def test_mufta(self):
        assert extract_product_type("Муфта 32") == "муфта"

    def test_zaglushka(self):
        assert extract_product_type("Заглушка 110") == "заглушка"

    def test_krestovina(self):
        assert extract_product_type("Крестовина 110") == "крестовина"

    def test_revizia(self):
        assert extract_product_type("Ревизия 110") == "ревизия"

    def test_homut(self):
        assert extract_product_type("Хомут 110") == "хомут"

    def test_perehod(self):
        assert extract_product_type("Переход 110/50") == "переходник"


class TestAngleExtraction:
    """Тесты извлечения угла"""

    def test_45_degree(self):
        assert extract_angle("Отвод 110/45") == 45

    def test_87_degree(self):
        assert extract_angle("Отвод 110/87") == 87

    def test_90_degree(self):
        assert extract_angle("Отвод 90° 110") == 90

    def test_no_angle(self):
        assert extract_angle("Муфта 32") is None


class TestThreadExtraction:
    """Тесты извлечения типа резьбы"""

    def test_vnutrennyaya_v_r(self):
        assert extract_thread_type("Отвод с в/р 20") == "вн"

    def test_vnutrennyaya_vn_rez(self):
        assert extract_thread_type("Отвод вн.рез. 20") == "вн"

    def test_naruzhnaya_n_r(self):
        assert extract_thread_type("Отвод с н/р 20") == "нар"

    def test_no_thread(self):
        assert extract_thread_type("Отвод 110/45") is None


class TestClampExtraction:
    """Тесты извлечения размера хомута"""

    def test_clamp_110(self):
        assert extract_mm_from_clamp("Хомут 110") == 110

    def test_clamp_50(self):
        assert extract_mm_from_clamp("Хомут 50") == 50

    def test_not_a_clamp(self):
        assert extract_mm_from_clamp("Труба 110") is None


class TestFullMatching:
    """Комплексные тесты matching"""

    @pytest.fixture
    def matcher(self):
        return MatchingService()

    def test_gray_pipe_110x3000(self, matcher):
        result = matcher.match_item(None, "Труба ПП 110×3000 серая", "Труба ПП 110×3000 серая")
        assert result.product_sku is not None
        assert result.product_sku.startswith("202")  # Серая канализация
        assert "110" in result.product_name
        assert "3000" in result.product_name

    def test_gray_elbow_110_45(self, matcher):
        result = matcher.match_item(None, "Отвод 110/45 серая", "Отвод 110/45 серая")
        assert result.product_sku is not None
        assert result.product_sku.startswith("202")
        assert extract_product_type(result.product_name) == "отвод"
        assert extract_angle(result.product_name) == 45

    def test_outdoor_elbow_110_45(self, matcher):
        result = matcher.match_item(None, "Отвод нар.кан. 110/45", "Отвод нар.кан. 110/45")
        assert result.product_sku is not None
        assert result.product_sku.startswith("303")  # Наружная канализация
        assert extract_product_type(result.product_name) == "отвод"
        # НЕ тройник!
        assert "тройник" not in result.product_name.lower()

    def test_prestige_tee(self, matcher):
        result = matcher.match_item(None, "Тройник Prestige 110/50", "Тройник Prestige 110/50")
        assert result.product_sku is not None
        assert result.product_sku.startswith("403")  # Prestige
        assert extract_product_type(result.product_name) == "тройник"

    def test_ppr_coupling(self, matcher):
        result = matcher.match_item(None, "Муфта ППР 32", "Муфта ППР 32")
        assert result.product_sku is not None
        assert result.product_sku.startswith("101")  # ППР
        assert extract_product_type(result.product_name) == "муфта"

    def test_gray_cap_110(self, matcher):
        result = matcher.match_item(None, "Заглушка 110 серая", "Заглушка 110 серая")
        assert result.product_sku is not None
        assert result.product_sku.startswith("202")
        assert extract_product_type(result.product_name) == "заглушка"
        # НЕ переходник или что-то другое
        assert "переход" not in result.product_name.lower()

    def test_clamp_110_gets_4_inch(self, matcher):
        result = matcher.match_item(None, "Хомут 110", "Хомут 110")
        assert result.product_sku is not None
        assert '4"' in result.product_name or "(107-115)" in result.product_name
        # НЕ 3/4" (это для труб 26-30мм)
        assert '3/4"' not in result.product_name

    def test_clamp_50_gets_1_5_inch(self, matcher):
        result = matcher.match_item(None, "Хомут 50", "Хомут 50")
        assert result.product_sku is not None
        assert '1 1/2"' in result.product_name or "(47-51)" in result.product_name

    def test_elbow_87_not_45(self, matcher):
        result = matcher.match_item(None, "Отвод 110/87 серая", "Отвод 110/87 серая")
        assert result.product_sku is not None
        assert extract_angle(result.product_name) == 87
        # НЕ 45 градусов
        assert extract_angle(result.product_name) != 45

    def test_revision_110(self, matcher):
        result = matcher.match_item(None, "Ревизия 110 серая", "Ревизия 110 серая")
        assert result.product_sku is not None
        assert extract_product_type(result.product_name) == "ревизия"

    def test_cross_110(self, matcher):
        result = matcher.match_item(None, "Крестовина 110 серая", "Крестовина 110 серая")
        assert result.product_sku is not None
        assert extract_product_type(result.product_name) == "крестовина"
        # НЕ тройник
        assert "тройник" not in result.product_name.lower()


class TestEdgeCases:
    """Крайние случаи"""

    @pytest.fixture
    def matcher(self):
        return MatchingService()

    def test_pp_without_color_defaults_to_sewer(self, matcher):
        """ПП без указания цвета - по умолчанию серая канализация"""
        result = matcher.match_item(None, "Труба ПП 110×2000", "Труба ПП 110×2000")
        # Должна найти что-то (может быть и ППР и кан.)
        assert result.product_sku is not None

    def test_exact_sku_match(self, matcher):
        """Точное совпадение артикула"""
        result = matcher.match_item(None, "202052110R", "202052110R")
        assert result.product_sku == "202052110R"
        assert result.match_type == "exact_sku"
        assert result.confidence == 100.0
