from typing import Any
from uuid import UUID

from backend.config import settings
from backend.models.schemas import MatchResult
from backend.services.matching_strategies.base import MatchingStrategy
from backend.utils.normalizers import normalize_name, normalize_sku


class ExactSkuStrategy(MatchingStrategy):
    def match(
        self,
        client_sku: str,
        client_name: str | None,
        products: list[dict[str, Any]],
        mappings: dict[str, Any],
    ) -> MatchResult | None:
        from backend.utils.normalizers import extract_sku_from_text

        norm_sku = normalize_sku(client_sku)

        # Также пробуем извлечь артикул из начала client_name
        extracted_sku = None
        if client_name:
            extracted = extract_sku_from_text(client_name)
            if extracted:
                extracted_sku = normalize_sku(extracted)

        for product in products:
            prod_sku = normalize_sku(product["sku"])
            if (norm_sku and prod_sku == norm_sku) or (
                extracted_sku and prod_sku == extracted_sku
            ):
                return MatchResult(
                    product_id=UUID(product["id"]),
                    product_sku=product["sku"],
                    product_name=product["name"],
                    confidence=settings.confidence_exact_sku,
                    match_type="exact_sku",
                    needs_review=False,
                    pack_qty=product.get("pack_qty", 1),
                )
        return None


class ExactNameStrategy(MatchingStrategy):
    def match(
        self,
        client_sku: str,
        client_name: str | None,
        products: list[dict[str, Any]],
        mappings: dict[str, Any],
    ) -> MatchResult | None:
        if not client_name:
            return None

        norm_name = normalize_name(client_name)
        if not norm_name:
            return None

        for product in products:
            if normalize_name(product["name"]) == norm_name:
                # Color Validation:
                # If client specified a color, product must match it.
                # Use extract_color from matching_helpers
                from backend.utils.matching_helpers import extract_color

                client_color = extract_color(client_name)
                prod_color = extract_color(product["name"])

                if client_color and prod_color and client_color != prod_color:
                    continue

                # Extra check for Prestige (White) vs Sewer (Gray) implicit
                if client_color == "white" and product["sku"].startswith("202"):
                    continue
                if client_color == "gray" and product["sku"].startswith("403"):
                    continue

                return MatchResult(
                    product_id=UUID(product["id"]),
                    product_sku=product["sku"],
                    product_name=product["name"],
                    confidence=settings.confidence_exact_name,
                    match_type="exact_name",
                    needs_review=False,
                    pack_qty=product.get("pack_qty", 1),
                )
        return None


class CachedMappingStrategy(MatchingStrategy):
    def match(
        self,
        client_sku: str,
        client_name: str | None,
        products: list[dict[str, Any]],
        mappings: dict[str, Any],
    ) -> MatchResult | None:
        norm_sku = normalize_sku(client_sku)

        if norm_sku in mappings:
            mapping = mappings[norm_sku]
            # Find the product object for the ID in the mapping
            product = next(
                (p for p in products if str(p["id"]) == str(mapping["product_id"])),
                None,
            )

            if product:
                return MatchResult(
                    product_id=UUID(product["id"]),
                    product_sku=product["sku"],
                    product_name=product["name"],
                    confidence=settings.confidence_exact_sku,  # Mappings are treated as exact/verified
                    match_type="cached_mapping",
                    needs_review=False,
                    pack_qty=product.get("pack_qty", 1),
                )
        return None
