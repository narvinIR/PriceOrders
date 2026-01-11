from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from rapidfuzz import fuzz
import logging

from backend.models.schemas import MatchResult
from backend.config import settings
from backend.utils.normalizers import (
    normalize_name, extract_pipe_size, extract_fitting_size,
    extract_thread_size, is_coupling_detachable, is_reducer
)
from backend.utils.matching_helpers import (
    normalize_equal_sizes, extract_thread_type, extract_product_type,
    extract_angle, normalize_angle, extract_mm_from_clamp,
    is_eco_product, filter_by_category, detect_client_category,
    clamp_fits_mm
)
from backend.constants import CRITICAL_TYPES
from backend.services.matching_strategies.base import MatchingStrategy

logger = logging.getLogger(__name__)

class HybridStrategy(MatchingStrategy):
    """
    Complex strategy involving fuzzy name matching combined with specific attribute filtering
    (size, angle, thread type, category, etc.)
    """
    
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
        
        # Helper to extract attributes once
        client_size = extract_pipe_size(client_name)
        client_fitting_size = extract_fitting_size(client_name)
        client_thread_size = extract_thread_size(client_name)
        client_cat = detect_client_category(client_name)
        client_type = extract_product_type(client_name)
        client_angle = extract_angle(client_name)
        
        # We perform full scan with fuzzy matching + filters
        matches = []
        for product in products:
            # --- START FILTERING ---
            # 1. Pipe Size
            if client_size:
                product_size = extract_pipe_size(product['name'])
                if product_size and product_size != client_size:
                    continue

            # 2. Thread Size
            if client_thread_size:
                product_thread = extract_thread_size(product['name'])
                if product_thread and product_thread != client_thread_size:
                    continue

            # 3. Fitting Size
            if client_fitting_size:
                product_fitting = extract_fitting_size(product['name'])
                if product_fitting:
                    norm_client = normalize_equal_sizes(client_fitting_size)
                    norm_product = normalize_equal_sizes(product_fitting)

                    if len(norm_client) == 1:
                        if norm_product[0] != norm_client[0]:
                            continue
                    elif norm_product != norm_client:
                        continue
            
            # --- END FILTERING ---

            # Fuzzy scoring
            prod_norm_name = normalize_name(product['name'])
            ratio = max(
                fuzz.token_sort_ratio(norm_name, prod_norm_name),
                fuzz.token_set_ratio(norm_name, prod_norm_name)
            )
            
            if ratio >= settings.fuzzy_threshold:
                matches.append((product, ratio))

        if not matches:
            return None

        # Apply post-filtering logic (logic copied from original matching.py)
        # TODO: Refactor these helper filtering functions to be more reusable or part of this class
        
        # 1. Critical Types
        if client_type:
            type_filtered = [m for m in matches if extract_product_type(m[0]['name']) == client_type]
            if type_filtered:
                matches = type_filtered
            elif client_type in CRITICAL_TYPES:
                # Critical type mismatch -> no match
                return None

        # 2. Angle
        if client_angle:
            normalized_angle = normalize_angle(client_angle)
            if normalized_angle:
                angle_filtered = [m for m in matches if extract_angle(m[0]['name']) == normalized_angle]
                if angle_filtered:
                    matches = angle_filtered

        # 3. Category
        effective_cat = client_cat or 'sewer'
        cat_filtered = filter_by_category(matches, effective_cat)
        if cat_filtered:
            matches = cat_filtered

        # Find best match
        best_match = max(matches, key=lambda x: x[1])
        product, score = best_match
        
        return MatchResult(
            product_id=UUID(product['id']),
            product_sku=product['sku'],
            product_name=product['name'],
            confidence=score,
            match_type="fuzzy_name", # or hybrid
            needs_review=score < 90,
            pack_qty=product.get('pack_qty', 1)
        )
