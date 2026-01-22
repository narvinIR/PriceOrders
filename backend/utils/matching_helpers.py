import re

from backend.constants import CLIENT_HINTS, PRODUCT_TYPE_MARKERS


def detect_client_category(client_name: str) -> str | None:
    """
    Определить категорию из запроса клиента using constants.
    """
    name = client_name.lower()

    # Reuse logic from original matching.py but using constants if preferred,
    # or keep the logic as is but moved here.
    # For safe refactoring, I will copy the logic 1:1 first.

    is_sewer = any(x in name for x in ["кан", "канализац", "сантех"])
    is_gray = "сер" in name

    # PERT
    if any(x in name for x in CLIENT_HINTS["pert"]):
        return "pert"

    # PND
    if any(x in name for x in CLIENT_HINTS["pnd"]):
        return "pnd"

    # Prestige
    if any(x in name for x in CLIENT_HINTS["prestige"]):
        return "prestige"
    if is_sewer and "бел" in name:
        return "prestige"

    # Outdoor
    if any(x in name for x in CLIENT_HINTS["outdoor"]):
        return "outdoor"

    # Sewer (gray)
    if is_gray or is_sewer:
        return "sewer"

    # PPR
    if any(x in name for x in CLIENT_HINTS["ppr"]):
        return "ppr"
    if "бел" in name and not is_sewer:
        return "ppr"

    return None


def extract_product_type(name: str) -> str | None:
    """
    Извлечь тип товара из названия using constants.
    """
    name_lower = name.lower()
    for marker, ptype in PRODUCT_TYPE_MARKERS:
        if marker in name_lower:
            return ptype
    return None


def extract_angle(name: str) -> int | None:
    """Извлечь угол из названия"""
    m = re.search(r"\b(15|30|45|67|87|90)\s*[°градус]?", name.lower())
    if m:
        return int(m.group(1))
    m = re.search(r"/\s*(15|30|45|67|87|90)\b", name.lower())
    if m:
        return int(m.group(1))
    return None


def normalize_angle(angle: int | None) -> int | None:
    if angle is None:
        return None
    if angle == 90:
        return 87
    return angle


def extract_thread_type(name: str) -> str | None:
    name_lower = name.lower()
    if any(
        x in name_lower
        for x in ["в/р", "вн.рез", "вн. рез", "вн рез", "внутр", "(вр)", "вр)", " вр "]
    ):
        return "вн"
    if any(
        x in name_lower
        for x in [
            "н/р",
            "нар.рез",
            "нар. рез",
            "нар рез",
            "наруж",
            "(нр)",
            "нр)",
            " нр ",
        ]
    ):
        return "нар"
    return None


def extract_mm_from_clamp(client_name: str) -> int | None:
    name = client_name.lower()
    if "хомут" not in name:
        return None
    patterns = [
        r"\bхомут\s+(?:в\s+комплекте\s+)?(\d+)",
        r"\bхомут\s+(?:для\s+)?(?:труб\w*\s+)?(\d+)",
        r"\bхомут\s*[∅dд]?\s*(\d+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, name)
        if m:
            mm = int(m.group(1))
            if 15 <= mm <= 200:
                return mm
    return None


def clamp_fits_mm(product_name: str, target_mm: int) -> bool:
    m = re.search(r"\((\d+)-(\d+)\)", product_name)
    if m:
        mm_min, mm_max = int(m.group(1)), int(m.group(2))
        return mm_min <= target_mm <= mm_max
    return False


def is_eco_product(name: str) -> bool:
    name_lower = name.lower()
    if "(1.8)" in name_lower:
        return False
    return "эко" in name_lower or "eko" in name_lower or "(2.2)" in name_lower


def normalize_equal_sizes(size: tuple) -> tuple:
    if not size:
        return size
    if len(size) >= 2 and len(set(size)) == 1:
        return (size[0],)
    return size


def filter_by_category(matches: list, client_cat: str | None) -> list:
    if not matches:
        return matches

    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    filtered = None
    if client_cat == "pert":
        filtered = [
            m
            for m in matches
            if get_product(m).get("sku", "").startswith("501")
            or "pert" in get_product(m)["name"].lower()
        ]
    elif client_cat == "pnd":
        filtered = [
            m
            for m in matches
            if get_product(m).get("sku", "").startswith("704")
            or "компресс" in get_product(m)["name"].lower()
        ]
    elif client_cat == "prestige":
        filtered = [
            m
            for m in matches
            if "малошум" in get_product(m).get("category", "").lower()
            or "prestige" in get_product(m)["name"].lower()
        ]
    elif client_cat == "outdoor":
        filtered = [
            m
            for m in matches
            if get_product(m).get("sku", "").startswith(("303", "604"))
            or "наружн" in get_product(m).get("category", "").lower()
            or "нар.кан" in get_product(m)["name"].lower()
            or "рифлен" in get_product(m)["name"].lower()
        ]
    elif client_cat == "ppr":
        filtered = [
            m
            for m in matches
            if "ппр" in get_product(m).get("category", "").lower()
            or "ппр" in get_product(m)["name"].lower()
        ]
    elif client_cat == "sewer":
        return [
            m
            for m in matches
            if get_product(m).get("sku", "").startswith("202")
            or (
                "серый" in get_product(m)["name"].lower()
                and "рифлен" not in get_product(m)["name"].lower()
            )
        ]
    else:
        # Default sewer logic
        sku_202 = [
            m for m in matches if get_product(m).get("sku", "").startswith("202")
        ]
        if sku_202:
            return sku_202
        filtered = [
            m
            for m in matches
            if (
                "канализац" in get_product(m).get("category", "").lower()
                and "малошум" not in get_product(m).get("category", "").lower()
                and "наружн" not in get_product(m).get("category", "").lower()
            )
            or "серый" in get_product(m)["name"].lower()
        ]

    return filtered if filtered else matches


def prepare_embedding_text(name: str, category: str = None) -> str:
    """
    Подготовка текста для embedding с усилением типа товара и категории.
    Тип товара и ключевые слова категории добавляются для повышения их веса.

    Args:
        name: Название товара
        category: Категория товара (опционально)
    """
    if not name:
        return ""

    from backend.utils.normalizers import normalize_name

    norm = normalize_name(name)
    product_type = extract_product_type(name)

    parts = []

    # Добавляем тип товара дважды для усиления веса
    if product_type:
        parts.append(product_type)
        parts.append(product_type)

    # Добавляем ключевые слова из категории
    if category:
        cat_lower = category.lower()
        if "малошум" in cat_lower:
            parts.extend(["малошумная", "белая", "prestige"])
        elif "наружн" in cat_lower:
            parts.extend(["наружная", "оранжевая", "рыжая"])
        elif "канализац" in cat_lower and "малошум" not in cat_lower:
            parts.extend(["серая", "внутренняя"])
        elif "ппр" in cat_lower or "полипроп" in cat_lower:
            parts.extend(["ппр", "полипропилен", "водопровод"])

    parts.append(norm)
    return " ".join(parts)
