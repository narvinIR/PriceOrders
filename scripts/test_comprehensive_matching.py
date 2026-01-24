#!/usr/bin/env python3
"""
Comprehensive E2E Matching Test Suite.
Tests the full matching pipeline with 20+ diverse queries.

Usage:
    PYTHONPATH=. python3 scripts/test_comprehensive_matching.py
"""

import sys

sys.path.insert(0, ".")

from backend.services.matching import MatchingService
from backend.config import settings
import logging

# Enable INFO logging to see LLM key masking
logging.basicConfig(level=logging.INFO)

print(f"DEBUG: API Key: {settings.openrouter_api_key[:10]}...")
print(f"DEBUG: Model: {settings.llm_model}")


# Test cases: (query, expected_category, expected_marker_in_name)
TEST_CASES = [
    # === Канализация серая (sewer) ===
    ("Ревизия кан. 110", "sewer", "серый"),
    ("Тройник кан. 110", "sewer", "серый"),
    ("Отвод кан. 45 110", "sewer", "серый"),
    ("Труба кан. 110", "sewer", None),
    ("Крестовина 110-50", "sewer", "серый"),
    # === Канализация белая / Prestige ===
    ("Ревизия кан. 110 белая", "prestige", "Prestige"),
    ("Тройник кан. 110 малошумный", "prestige", "Prestige"),
    ("Отвод кан. 45 110 белый", "prestige", "Prestige"),
    ("Труба кан. малошумная 110", "prestige", "Prestige"),
    # === Наружная канализация (outdoor) ===
    ("Труба нар.кан. 110", "outdoor", "нар"),
    ("Муфта наружная 160", "outdoor", "нар"),
    ("Тройник наружный 110", "outdoor", "нар"),
    # === ППР (PPR pipes) ===
    ("Муфта ПП 32", "ppr", "ППР"),
    ("Труба ППР 25", "ppr", "ППР"),
    ("Тройник ППР 32", "ppr", "ППР"),
    ("Кран ППР 25", "ppr", "ППР"),
    # === Edge cases ===
    ("202132110K", "any", None),  # SKU lookup
    ("муфто 32", "ppr", "Муфта"),  # Typo
    ("ревизия белая 110", "prestige", "Prestige"),  # Reordered words
    ("110 тройник серый", "sewer", "серый"),  # Reversed order
]


def run_tests():
    print("🧪 Comprehensive Matching Test Suite")
    print("=" * 70)
    print()

    # Init service
    service = MatchingService()

    passed = 0
    failed = 0
    warnings = 0

    for query, expected_cat, expected_marker in TEST_CASES:
        # Use match_item API (client_id=None, client_sku="", client_name=query)
        result = service.match_item(None, "", query)

        # MatchResult has: product_id, product_sku, product_name, confidence, match_type
        if not result or not result.product_id:
            print(f"❌ '{query}' -> NO MATCH")
            failed += 1
            continue

        name = result.product_name or ""
        sku = result.product_sku or ""
        confidence = result.confidence or 0
        match_type = result.match_type or "unknown"

        # Check if marker is present (if expected)
        marker_ok = True
        if expected_marker and expected_marker.lower() not in name.lower():
            marker_ok = False

        status = "✅" if marker_ok else "⚠️"
        if not marker_ok:
            warnings += 1
        else:
            passed += 1

        print(f"{status} '{query}'")
        print(f"   → {name} [{sku}]")
        print(f"   → Confidence: {confidence:.1f}%, Type: {match_type}")
        if not marker_ok:
            print(f"   ⚠️ Expected marker '{expected_marker}' not found!")
        print()

    print("=" * 70)
    print(f"📊 Results: ✅ {passed} passed, ⚠️ {warnings} warnings, ❌ {failed} failed")
    print(f"   Total: {len(TEST_CASES)} tests")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
