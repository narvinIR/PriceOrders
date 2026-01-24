import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())

from backend.services.matching_strategies.hybrid import HybridStrategy
from backend.services.embeddings import get_embedding_matcher


async def test_hybrid():
    print("🧠 Testing Hybrid Strategy...")
    matcher = HybridStrategy()

    # Needs products list for fuzzy fallback part of hybrid
    # But hybrid mainly uses pgvector via embedding_matcher

    query = "Заглушка компрессионная 40 Tebo/UNIO"
    print(f"🔎 Query: '{query}'")

    # 1. Test embedding generation
    em = get_embedding_matcher()
    vec = em._generate_embedding(query)
    if vec:
        print(f"✅ Embedding generated (len={len(vec)})")
    else:
        print("❌ Embedding generation failed")
        return

    # 2. Test DB search
    results = em.search(query, top_k=5, min_score=0.1)  # low score to see anything
    print(f"Postgres Results: {len(results)}")
    for r in results:
        print(f"  - {r[0]['name']} (Score: {r[1]:.3f})")

    # 3. Test Full Strategy
    # Mock products list (hybrid uses it for fuzzy reranking)
    products = [
        {
            "id": "00000000-0000-0000-0000-000000000000",
            "sku": "704010040T",
            "name": "Заглушка компрессионная 40 Jakko",
        }
    ]

    match = matcher.match(None, query, products, {})
    if match:
        print(f"✅ Hybrid Match: {match.product_sku} ({match.confidence}%)")
    else:
        print("❌ Hybrid Strategy returned None")


if __name__ == "__main__":
    asyncio.run(test_hybrid())
