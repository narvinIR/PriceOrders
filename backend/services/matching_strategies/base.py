from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from backend.models.schemas import MatchResult

class MatchingStrategy(ABC):
    """Abstract base class for matching strategies."""

    @abstractmethod
    def match(
        self,
        client_sku: str,
        client_name: Optional[str],
        products: List[Dict[str, Any]],
        mappings: Dict[str, Any]
    ) -> Optional[MatchResult]:
        """
        Attempt to match a client item to a product.

        Args:
            client_sku: The client's SKU (article number).
            client_name: The client's product name.
            products: List of available products from the catalog.
            mappings: Dictionary of existing confirmed mappings.

        Returns:
            MatchResult if a match is found, None otherwise.
        """
        pass
