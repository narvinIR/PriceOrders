from typing import Any
from uuid import UUID

from rapidfuzz import fuzz

from backend.config import settings
from backend.models.schemas import MatchResult
from backend.services.matching_strategies.base import MatchingStrategy
from backend.utils.normalizers import normalize_sku


class FuzzySkuStrategy(MatchingStrategy):
    def match(
        self,
        client_sku: str,
        client_name: str | None,
        products: list[dict[str, Any]],
        mappings: dict[str, Any]
    ) -> MatchResult | None:
        from backend.utils.normalizers import extract_sku_from_text

        norm_sku = normalize_sku(client_sku)

        # Fallback: извлечь артикул из client_name если client_sku пустой
        if not norm_sku and client_name:
            extracted = extract_sku_from_text(client_name)
            if extracted:
                norm_sku = normalize_sku(extracted)

        best_sku_match = None
        best_sku_ratio = 0

        for product in products:
            prod_norm_sku = normalize_sku(product['sku'])
            ratio = fuzz.ratio(norm_sku, prod_norm_sku)
            if ratio > best_sku_ratio and ratio >= 90:
                best_sku_ratio = ratio
                best_sku_match = product

        if best_sku_match and best_sku_ratio >= 90:
            return MatchResult(
                product_id=UUID(best_sku_match['id']),
                product_sku=best_sku_match['sku'],
                product_name=best_sku_match['name'],
                confidence=settings.confidence_fuzzy_sku * (best_sku_ratio / 100),
                match_type="fuzzy_sku",
                needs_review=best_sku_ratio < 95,
                pack_qty=best_sku_match.get('pack_qty', 1)
            )
        return None
