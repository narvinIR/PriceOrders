from typing import Optional, List, Dict, Any
from uuid import UUID
from backend.models.schemas import MatchResult
from backend.config import settings
from backend.utils.normalizers import normalize_sku, normalize_name
from backend.services.matching_strategies.base import MatchingStrategy

class ExactSkuStrategy(MatchingStrategy):
    def match(
        self,
        client_sku: str,
        client_name: Optional[str],
        products: List[Dict[str, Any]],
        mappings: Dict[str, Any]
    ) -> Optional[MatchResult]:
        norm_sku = normalize_sku(client_sku)
        
        for product in products:
            if normalize_sku(product['sku']) == norm_sku:
                return MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=settings.confidence_exact_sku,
                    match_type="exact_sku",
                    needs_review=False,
                    pack_qty=product.get('pack_qty', 1)
                )
        return None

class ExactNameStrategy(MatchingStrategy):
    def match(
        self,
        client_sku: str,
        client_name: Optional[str],
        products: List[Dict[str, Any]],
        mappings: Dict[str, Any]
    ) -> Optional[MatchResult]:
        if not client_name:
            return None
            
        norm_name = normalize_name(client_name)
        if not norm_name:
            return None

        for product in products:
            if normalize_name(product['name']) == norm_name:
                return MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=settings.confidence_exact_name,
                    match_type="exact_name",
                    needs_review=False,
                    pack_qty=product.get('pack_qty', 1)
                )
        return None

class CachedMappingStrategy(MatchingStrategy):
    def match(
        self,
        client_sku: str,
        client_name: Optional[str],
        products: List[Dict[str, Any]],
        mappings: Dict[str, Any]
    ) -> Optional[MatchResult]:
        norm_sku = normalize_sku(client_sku)
        
        if norm_sku in mappings:
            mapping = mappings[norm_sku]
            # Find the product object for the ID in the mapping
            product = next((p for p in products if str(p['id']) == str(mapping['product_id'])), None)
            
            if product:
                return MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=settings.confidence_exact_sku, # Mappings are treated as exact/verified
                    match_type="cached_mapping",
                    needs_review=False,
                    pack_qty=product.get('pack_qty', 1)
                )
        return None
