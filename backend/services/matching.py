import logging
from threading import Lock
from uuid import UUID

from backend.config import settings

# We also need constants if they were used externally? No, usually functions.
from backend.models.database import get_supabase_client
from backend.models.schemas import MatchResult
from backend.services.embeddings import get_embedding_matcher

# Import Strategies
from backend.services.matching_strategies.exact import (
    CachedMappingStrategy,
    ExactNameStrategy,
    ExactSkuStrategy,
)
from backend.services.matching_strategies.fuzzy import FuzzySkuStrategy
from backend.services.matching_strategies.hybrid import HybridStrategy
from backend.services.matching_strategies.llm import LlmStrategy

# Re-export helpers for backward compatibility
from backend.utils.matching_helpers import (
    extract_product_type,
)
from backend.utils.normalizers import normalize_sku

logger = logging.getLogger(__name__)


class MatchingService:
    """Refactored MatchingService using Strategy Pattern"""

    def __init__(self):
        self.db = get_supabase_client()
        self._products_cache = None
        self._mappings_cache = {}
        self._mappings_lock = Lock()
        self._stats_lock = Lock()
        self._embedding_matcher = get_embedding_matcher()
        self._stats = {
            "total": 0,
            "exact_sku": 0,
            "exact_name": 0,
            "cached_mapping": 0,
            "fuzzy_sku": 0,
            "fuzzy_name": 0,
            "llm_match": 0,
            "not_found": 0,
            "total_confidence": 0.0,
        }

        # Initialize Strategies
        self.strategies = [
            ExactSkuStrategy(),
            ExactNameStrategy(),
            CachedMappingStrategy(),
            FuzzySkuStrategy(),
            HybridStrategy(),
            LlmStrategy(),
        ]

    def _load_products(self) -> list[dict]:
        """Загрузка каталога товаров и построение embedding индекса"""
        if self._products_cache is None:
            response = self.db.table("products").select("*").execute()
            self._products_cache = response.data or []
            if settings.enable_ml_matching:
                if self._products_cache and not self._embedding_matcher.is_ready:
                    # EmbeddingMatcher (Relay) does not need build_index
                    pass
        return self._products_cache

    def _load_client_mappings(self, client_id: UUID | None) -> dict:
        """Загрузка маппингов клиента (thread-safe)"""
        if client_id is None:
            return {}
        client_key = str(client_id)
        with self._mappings_lock:
            if client_key not in self._mappings_cache:
                response = (
                    self.db.table("mappings")
                    .select("client_sku, product_id, confidence, match_type")
                    .eq("client_id", str(client_id))
                    .eq("verified", True)
                    .execute()
                )
                self._mappings_cache[client_key] = {
                    normalize_sku(m["client_sku"]): m for m in (response.data or [])
                }
            return self._mappings_cache[client_key]

    def clear_cache(self):
        """Очистка кэша (thread-safe)"""
        self._products_cache = None
        with self._mappings_lock:
            self._mappings_cache = {}

    def get_stats(self) -> dict:
        """Получить статистику matching"""
        stats = self._stats.copy()
        if stats["total"] > 0:
            stats["avg_confidence"] = round(
                stats["total_confidence"] / stats["total"], 1
            )
            stats["success_rate"] = round(
                100 * (stats["total"] - stats["not_found"]) / stats["total"], 1
            )
        else:
            stats["avg_confidence"] = 0.0
            stats["success_rate"] = 0.0
        return stats

    def reset_stats(self):
        """Сбросить статистику (thread-safe)"""
        with self._stats_lock:
            for key in self._stats:
                self._stats[key] = 0 if isinstance(self._stats[key], int) else 0.0

    def save_mapping(
        self,
        client_id: UUID,
        client_sku: str,
        product_id: UUID,
        confidence: float,
        match_type: str,
        verified: bool = False,
    ):
        """Сохранение маппинга в БД (UPSERT)"""
        from datetime import datetime

        data = {
            "client_id": str(client_id),
            "client_sku": client_sku,
            "product_id": str(product_id),
            "confidence": confidence,
            "match_type": match_type,
            "verified": verified,
        }
        if verified:
            data["verified_at"] = datetime.utcnow().isoformat()

        self.db.table("mappings").upsert(
            data, on_conflict="client_id,client_sku"
        ).execute()

        # Инвалидируем кэш клиента
        client_key = str(client_id)
        with self._mappings_lock:
            if client_key in self._mappings_cache:
                del self._mappings_cache[client_key]

    def _update_stats(self, match: MatchResult):
        """Обновить статистику после match (thread-safe)"""
        with self._stats_lock:
            self._stats["total"] += 1
            self._stats["total_confidence"] += match.confidence
            if match.match_type in self._stats:
                self._stats[match.match_type] += 1

    def _finalize_match(self, match: MatchResult) -> MatchResult:
        """Финализировать результат: логирование + статистика"""
        self._update_stats(match)
        if match.product_id:
            logger.info(
                f"Matched: {match.match_type} @ {match.confidence:.0f}% "
                f"→ {match.product_sku}"
            )
        else:
            logger.warning(f"Not found: {match.match_type}")
        return match

    def match_item(
        self, client_id: UUID | None, client_sku: str, client_name: str = None
    ) -> MatchResult:
        """
        Refactored match_item using strategies.
        """
        logger.debug(f"Matching: sku={client_sku!r}, name={client_name!r}")

        # HEURISTIC: If name is empty but SKU looks like a description (has spaces, long), use SKU as name
        if (
            not client_name
            and client_sku
            and len(client_sku) > 10
            and " " in client_sku
        ):
            client_name = client_sku
            # Keep client_sku as is, but now Strategy has a name to work with
            logger.info(f"Swap: using SKU as name for matching: {client_name}")

        products = self._load_products()
        mappings = self._load_client_mappings(client_id)

        # Iterate through strategies
        for strategy in self.strategies:
            match_result = strategy.match(client_sku, client_name, products, mappings)
            if match_result:
                return self._finalize_match(match_result)

        # Fallback if no match found
        # TODO: Add LLM fallback strategy if needed, but currently not in the list of moved/refactored parts explicitly
        # The original code had LLM matching as level 6. I should add it as a strategy or keep it here?
        # Ideally it should be a strategy: LlmStrategy.
        # But I didn't create LlmStrategy yet.
        # I will keep logic for LLM here or create LlmStrategy quickly?
        # Plan said: Exact, Fuzzy, Hybrid.
        # I should probably just return "Not Found" for now as per strict plan,
        # BUT losing LLM matching would be a regression.

        # Let's check original code for LLM.
        # It was:
        # # Level 6: LLM verification (если confidence < 75%) → ≤75%
        # ...

        # I will implement LLM fallback here directly to be safe, or as a strategy locally defined?
        # For minimal complexity, I'll add LLM logic back here.
        # Actually, let's look at `backend/services/llm_matcher.py`, it has `get_llm_matcher`.

        from backend.services.llm_matcher import get_llm_matcher

        get_llm_matcher()
        # Note: Original code logic for LLM
        # It ran if nothing else matched or confidence was low?
        # Actually original code returned early on matches.
        # So here, if we fall through strategies, it means no match found (or low confidence if strategies had thresholds, but my strategies return MatchResult only on success).

        # Wait, original fuzzy strategy had:
        # if best_sku_match and best_sku_ratio >= 90: return ...

        # My strategies return None if threshold not met.
        # So if we are here, no strategy succeeded.

        # Try LLM
        # (This is a simplified assumption, original code might have tried LLM only if hybrid failed?)
        # Yes, original code:
        # 1. Exact SKU
        # 2. Exact Name
        # 3. Cache
        # 4. Fuzzy SKU
        # 5. Hybrid (PGVector + Fuzzy Hybrid)
        # 6. LLM

        # So if strategies 1-5 return None, we try LLM.
        # EXCEPT: Original code had logic where Hybrid could return nothing? Yes.

        # There was:
        # ... (Levels 1-5 logic)
        # if matches: ... return ...

        # So yes, if we reach here, we try LLM.

        # FIXME: I cannot easily incorporate LLM logic without importing it or making a strategy.
        # I'll check if I can just assume "Not Found" if LLM is not critical or not requested to be refactored?
        # Use simple return Not Found for now to respect strict refactoring of *existing* logic into strategies.
        # BUT LLM is part of existing logic.
        # The plan didn't explicitly mention LLM strategy.
        # I will add a `LlmStrategy` quickly to `backend/services/matching_strategies/llm.py`?
        # Or just inline it here. Inlining is safer to avoid creating files not in plan.

        # Inline LLM Logic (Simplified):
        # We need settings.enable_llm_matching check?
        # Original code didn't seem to check enable_llm_matching in match_item explicitly,
        # but `llm_matcher.py` might handle it or `settings` has it.
        # Original code used `backend/services/llm_matcher.py`.

        return self._finalize_match(
            MatchResult(
                product_id=None,
                product_sku=client_sku,
                product_name=client_name,
                confidence=0.0,
                match_type="not_found",
                needs_review=True,
            )
        )


# Functions required for backward compatibility imports
def filter_by_product_type(matches: list, client_type: str | None) -> list:
    if not matches or not client_type or len(matches) <= 1:
        return matches
    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    filtered = [
        m
        for m in matches
        if extract_product_type(get_product(m)["name"]) == client_type
    ]
    return filtered if filtered else matches


# Add other filters if they were used externally...
# Checking grep results:
# test_e2e_matching.py imports: (MatchingService) - NO, it imports `from backend.services.matching import (`
# then lists...
# I need to know WHAT test_e2e_matching imports.
# I'll read test_e2e_matching.py to see what it imports.
