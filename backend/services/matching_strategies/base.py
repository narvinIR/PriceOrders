from abc import ABC, abstractmethod
from typing import Any

from backend.models.schemas import MatchResult


class MatchingStrategy(ABC):
    """Abstract base class for matching strategies."""

    @abstractmethod
    def match(
        self,
        client_sku: str,
        client_name: str | None,
        products: list[dict[str, Any]],
        mappings: dict[str, Any]
    ) -> MatchResult | None:
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
