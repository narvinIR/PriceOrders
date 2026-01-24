import logging
from typing import Any
from uuid import UUID

from rapidfuzz import fuzz

from backend.config import settings
from backend.constants import CRITICAL_TYPES
from backend.models.schemas import MatchResult
from backend.services.embeddings import get_embedding_matcher
from backend.services.matching_strategies.base import MatchingStrategy
from backend.utils.matching_helpers import (
    detect_client_category,
    extract_angle,
    extract_color,
    extract_product_type,
    filter_by_category,
    normalize_angle,
    normalize_equal_sizes,
)
from backend.utils.normalizers import (
    extract_fitting_size,
    extract_pipe_size,
    extract_thread_size,
    normalize_name,
)

logger = logging.getLogger(__name__)


class HybridStrategy(MatchingStrategy):
    """
    Complex strategy involving fuzzy name matching combined with specific attribute filtering
    (size, angle, thread type, category, etc.)
    """

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

        # Helper to extract attributes once
        client_size = extract_pipe_size(client_name)
        client_fitting_size = extract_fitting_size(client_name)
        client_thread_size = extract_thread_size(client_name)
        client_cat = detect_client_category(client_name)
        client_type = extract_product_type(client_name)
        client_angle = extract_angle(client_name)

        # --- SEMANTIC PRE-FILTERING (pgvector) ---
        # Use embedding matcher to narrow down candidates before fuzzy matching
        # This reduces O(N) to O(k) where k << N, significantly improving performance
        embedding_matcher = get_embedding_matcher()
        candidate_products = products  # Default: use all products

        # Map product ID to its semantic score for lookup
        semantic_scores = {}

        try:
            # Get top candidates from semantic search
            semantic_results = embedding_matcher.search(
                client_name, top_k=50, min_score=0.4
            )
            if semantic_results:
                # Extract IDs and scores
                for prod, score in semantic_results:
                    semantic_scores[str(prod["id"]).lower()] = score

                candidate_ids = set(semantic_scores.keys())

                # Filter products to only those found by semantic search
                filtered = [
                    p for p in products if str(p.get("id", "")).lower() in candidate_ids
                ]

                if filtered:
                    candidate_products = filtered
                    logger.debug(
                        f"Semantic pre-filter: {len(products)} -> {len(candidate_products)} candidates"
                    )
                else:
                    logger.warning(
                        f"Semantic found {len(candidate_ids)} items but no ID validation match in loaded products."
                    )
        except Exception as e:
            # Fallback to full scan if embedding search fails
            logger.warning(f"Semantic pre-filter failed, using full scan: {e}")

        # We perform scan with fuzzy matching + filters on pre-filtered candidates
        matches = []
        for product in candidate_products:
            # Retrieve semantic score if available
            sem_score = semantic_scores.get(str(product.get("id", "")).lower(), 0.0)

            # --- START FILTERING ---
            # 1. Pipe Size
            if client_size:
                product_size = extract_pipe_size(product["name"])
                if product_size and product_size != client_size:
                    logger.debug(
                        f"Filter size mismatch: {client_size} vs {product_size} for {product['name']}"
                    )
                    continue

            # 2. Thread Size
            if client_thread_size:
                product_thread = extract_thread_size(product["name"])
                # STRICT MATCHING: If client specifies thread, product MUST have thread
                if not product_thread:
                    continue
                if product_thread != client_thread_size:
                    logger.debug(
                        f"Filter thread mismatch: {client_thread_size} vs {product_thread} for {product['name']}"
                    )
                    continue

            # 3. Fitting Size
            if client_fitting_size:
                product_fitting = extract_fitting_size(product["name"])
                if product_fitting:
                    norm_client = normalize_equal_sizes(client_fitting_size)
                    norm_product = normalize_equal_sizes(product_fitting)

                    if len(norm_client) == 1:
                        if norm_product[0] != norm_client[0]:
                            logger.debug(
                                f"Filter fitting mismatch for {product['name']}"
                            )
                            continue
                    elif norm_product != norm_client:
                        logger.debug(f"Filter fitting mismatch for {product['name']}")
                        continue

            # 4. Color (Strict if specified)
            # Fix for White (Prestige) vs Gray (Sewer)
            # If client specifies "белый", we skip "серый" products completely
            if extract_color(client_name):
                client_color = extract_color(client_name)
                product_color = extract_color(product["name"])
                # If product also has a color, they must match
                if product_color and client_color != product_color:
                    continue

                # Extra check for Prestige vs Sewer implicit colors
                # "Sewer" usually means Gray, "Prestige" usually means White
                # If client wants White/Prestige, skip 202... (Sewer Gray)
                if client_color == "white" and product["sku"].startswith("202"):
                    continue
                # If client wants Gray/Sewer, skip 403... (Prestige White)
                if client_color == "gray" and product["sku"].startswith("403"):
                    continue
                # If client wants Red/Outdoor, skip 202/403
                if client_color == "red" and (
                    product["sku"].startswith("202") or product["sku"].startswith("403")
                ):
                    continue

            # --- END FILTERING ---

            # Fuzzy scoring
            prod_norm_name = normalize_name(product["name"])
            fuzzy_score = (
                fuzz.token_sort_ratio(norm_name, prod_norm_name)
                + fuzz.token_set_ratio(norm_name, prod_norm_name)
            ) / 2

            # Hybrid Score Calculation
            # If semantic score is VERY high (>0.85), trust it more even if fuzzy is lower (e.g. noise like 'Tebo/UNIO')
            # 0.85 semantic ~= 85 fuzzy

            final_score = fuzzy_score
            match_source = "fuzzy"

            if sem_score > 0.85:
                # Upboost fuzzy score if semantic is strong and fuzzy is at least decent (>40)
                # This allows bypassing strict 70 threshold for "meaning" matches
                if fuzzy_score > 40:
                    final_score = max(fuzzy_score, sem_score * 100)
                    match_source = "semantic_boost"

            if final_score >= settings.fuzzy_threshold:
                matches.append((product, final_score, match_source))

        if not matches:
            return None

        # Apply post-filtering logic (logic copied from original matching.py)
        # TODO: Refactor these helper filtering functions to be more reusable or part of this class

        # 1. Critical Types
        if client_type:
            type_filtered = [
                m for m in matches if extract_product_type(m[0]["name"]) == client_type
            ]
            if type_filtered:
                matches = type_filtered
            elif client_type in CRITICAL_TYPES:
                # Critical type mismatch -> no match
                return None

        # 2. Angle
        if client_angle:
            normalized_angle = normalize_angle(client_angle)
            if normalized_angle:
                angle_filtered = [
                    m
                    for m in matches
                    if extract_angle(m[0]["name"]) == normalized_angle
                ]
                if angle_filtered:
                    matches = angle_filtered

        # 3. Category
        effective_cat = client_cat or "sewer"
        cat_filtered = filter_by_category(matches, effective_cat)
        if cat_filtered:
            matches = cat_filtered

        # Find best match
        best_match = max(matches, key=lambda x: x[1])
        # Handle 2 or 3 element tuples (backward compat logic just in case)
        if len(best_match) == 3:
            product, score, match_type_suffix = best_match
        else:
            product, score = best_match
            match_type_suffix = "fuzzy"

        return MatchResult(
            product_id=UUID(product["id"]),
            product_sku=product["sku"],
            product_name=product["name"],
            confidence=score,
            match_type="fuzzy_name",  # or hybrid
            needs_review=score < 90,
            pack_qty=product.get("pack_qty", 1),
        )
