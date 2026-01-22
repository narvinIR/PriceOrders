"""
Unit тесты для backend/utils/normalizers.py
"""

import sys

sys.path.insert(0, "/home/dimas/projects/PriceOrders")

from backend.utils.normalizers import (
    expand_synonyms,
    extract_fitting_size,
    extract_numeric_sku,
    extract_pipe_size,
    normalize_name,
    normalize_sku,
    tokenize_name,
)


class TestNormalizeSku:
    """Тесты для normalize_sku()"""

    def test_uppercase(self):
        assert normalize_sku("jk-pp-110") == "JKPP110"

    def test_remove_separators(self):
        assert normalize_sku("JK-PP.110") == "JKPP110"
        assert normalize_sku("JK/PP_110") == "JKPP110"
        assert normalize_sku("JK PP 110") == "JKPP110"

    def test_strip_leading_zeros(self):
        assert normalize_sku("007890") == "7890"
        assert normalize_sku("0") == "0"
        assert normalize_sku("000") == "0"

    def test_empty(self):
        assert normalize_sku("") == ""
        assert normalize_sku(None) == ""


class TestNormalizeName:
    """Тесты для normalize_name()"""

    def test_lowercase(self):
        result = normalize_name("ТРУБА ПП")
        assert "труба" in result

    def test_remove_brand_jk(self):
        result = normalize_name("Jk Труба ПП 110")
        assert "jk" not in result.lower()

    def test_remove_brand_jakko(self):
        result = normalize_name("Jakko Труба ПП 110")
        assert "jakko" not in result.lower()

    def test_keep_prestige_line(self):
        # Prestige - линейка малошумной канализации, НЕ удаляем
        result = normalize_name("Prestige Труба малошумная 110")
        # 'малошумн*' конвертируется в 'prestige'
        assert "prestige" in result.lower()

    def test_remove_pack_qty(self):
        result = normalize_name("Отвод 50 (уп 20 шт)")
        assert "уп" not in result
        assert "20" not in result or "шт" not in result

    def test_keep_metrazh(self):
        """Метраж (50 м) должен сохраняться - это разные товары"""
        result = normalize_name("Труба 110 (50 м)")
        assert "50" in result

    def test_normalize_separators(self):
        """Все разделители → ×"""
        assert "×" in normalize_name("Труба 110×2000") or "110 2000" in normalize_name(
            "Труба 110×2000"
        )

    def test_normalize_pn(self):
        """PN 20, PN-20, PN20 → pn20"""
        assert "pn20" in normalize_name("Труба PN 20")
        assert "pn20" in normalize_name("Труба PN-20")
        assert "pn20" in normalize_name("Труба PN20")

    def test_empty(self):
        assert normalize_name("") == ""
        assert normalize_name(None) == ""


class TestExpandSynonyms:
    """Тесты для expand_synonyms()"""

    def test_material_pp(self):
        result = expand_synonyms("труба пп 32")
        assert "полипропилен" in result

    def test_material_pe(self):
        result = expand_synonyms("труба пэ 32")
        assert "полиэтилен" in result

    def test_material_ppr(self):
        result = expand_synonyms("труба ппр 32")
        assert "полипропилен" in result

    def test_product_koleno(self):
        result = expand_synonyms("колено 50")
        assert "отвод" in result

    def test_product_ugol(self):
        result = expand_synonyms("угол 50")
        assert "отвод" in result

    def test_product_ugolnik(self):
        result = expand_synonyms("угольник 50")
        assert "отвод" in result

    def test_thread_vn_rez(self):
        result = expand_synonyms("муфта с вн.рез.")
        assert "вн рез" in result

    def test_thread_nar_rez(self):
        result = expand_synonyms("муфта с нар.рез.")
        assert "нар рез" in result

    def test_thread_v_r(self):
        result = expand_synonyms("муфта в/р 32")
        assert "вн рез" in result

    def test_thread_n_r(self):
        result = expand_synonyms("муфта н/р 32")
        assert "нар рез" in result

    def test_maloshum(self):
        result = expand_synonyms("труба малошум. 110")
        assert "малошумная" in result

    def test_nar_kan(self):
        result = expand_synonyms("труба нар.кан. 160")
        assert "наружная канализация" in result

    def test_priority_longer_first(self):
        """Длинные синонимы должны заменяться раньше коротких"""
        result = expand_synonyms("нар.кан.")
        assert "наружная канализация" in result
        assert "канализационн" not in result


class TestExtractPipeSize:
    """Тесты для extract_pipe_size()"""

    def test_standard_separator(self):
        assert extract_pipe_size("Труба 110×2000") == (110, 2000)

    def test_x_separator(self):
        assert extract_pipe_size("Труба 110x2000") == (110, 2000)

    def test_asterisk_separator(self):
        assert extract_pipe_size("Труба 110*2000") == (110, 2000)

    def test_dash_separator(self):
        assert extract_pipe_size("Труба 110-2000") == (110, 2000)

    def test_with_spaces(self):
        assert extract_pipe_size("Труба 110 × 2000") == (110, 2000)

    def test_various_sizes(self):
        assert extract_pipe_size("Труба 32×500") == (32, 500)
        assert extract_pipe_size("Труба 50×1500") == (50, 1500)
        assert extract_pipe_size("Труба 160×3000") == (160, 3000)

    def test_invalid_too_small(self):
        """Диаметр меньше 16мм - не валидно"""
        assert extract_pipe_size("Труба 10×500") is None

    def test_invalid_too_short(self):
        """Длина меньше 100мм - не валидно (это угол)"""
        assert extract_pipe_size("Отвод 50×45") is None

    def test_fitting_not_pipe(self):
        """Фитинги с углом не должны извлекаться"""
        assert extract_pipe_size("Отвод 50×45°") is None

    def test_empty(self):
        assert extract_pipe_size("") is None
        assert extract_pipe_size(None) is None


class TestExtractFittingSize:
    """Тесты для extract_fitting_size()"""

    def test_single_size(self):
        assert extract_fitting_size("Муфта ППР 32") == (32,)

    def test_two_sizes(self):
        assert extract_fitting_size("Переход 50×32") == (50, 32)

    def test_three_sizes(self):
        assert extract_fitting_size("Тройник 63×50×63") == (63, 50, 63)

    def test_empty(self):
        assert extract_fitting_size("") is None
        assert extract_fitting_size(None) is None


class TestExtractNumericSku:
    """Тесты для extract_numeric_sku()"""

    def test_extract_digits(self):
        assert extract_numeric_sku("JK-PP-110") == "110"

    def test_strip_leading_zeros(self):
        assert extract_numeric_sku("007890") == "7890"

    def test_only_letters(self):
        assert extract_numeric_sku("ABC") == "0"

    def test_empty(self):
        assert extract_numeric_sku("") == ""


class TestTokenizeName:
    """Тесты для tokenize_name()"""

    def test_basic(self):
        tokens = tokenize_name("Труба ПП 110")
        assert "труба" in tokens
        assert "полипропилен" in tokens
        assert "110" in tokens

    def test_remove_stop_words(self):
        tokens = tokenize_name("Труба для воды с фланцем")
        assert "для" not in tokens
        assert "с" not in tokens

    def test_remove_units(self):
        tokens = tokenize_name("Труба 110 мм")
        assert "мм" not in tokens
