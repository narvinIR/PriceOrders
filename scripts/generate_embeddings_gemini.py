#!/usr/bin/env python3
"""
Generate embeddings for all products using Google Gemini API via Cloudflare Relay.
Run this once after deployment to populate the database.

v2: Added retry logic with exponential backoff for reliability.

Usage:
    PYTHONPATH=. python3 scripts/generate_embeddings_gemini.py
"""

import os
import time
from typing import List

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

from backend.utils.matching_helpers import prepare_embedding_text

# Load env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Cloudflare Relay (no API key needed - embedded in worker)
GEMINI_RELAY_URL = "https://gemini-api-relay.schmidvili1.workers.dev"
EMBEDDING_MODEL = "models/text-embedding-004"

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0
MAX_BACKOFF = 30.0

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

# Init clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Supabase connected")
print(f"✅ Using Gemini Relay: {GEMINI_RELAY_URL}")
print(
    f"⚙️  Retry config: {MAX_RETRIES} attempts, backoff {INITIAL_BACKOFF}-{MAX_BACKOFF}s"
)


def get_products(only_missing: bool = True):
    """Fetch products (optionally only those without embeddings)."""
    query = supabase.table("products").select("id, name, sku, category")
    if only_missing:
        # Get products where embedding is null
        query = query.is_("embedding", "null")
    response = query.execute()
    return response.data


def generate_embedding(text: str) -> List[float] | None:
    """Generate embedding using Google Gemini API via Cloudflare Relay.

    Includes retry logic with exponential backoff.
    """
    url = f"{GEMINI_RELAY_URL}/v1beta/{EMBEDDING_MODEL}:embedContent"
    payload = {
        "model": EMBEDDING_MODEL,
        "content": {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_DOCUMENT",
    }

    backoff = INITIAL_BACKOFF
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60.0,  # Increased timeout
            )

            if response.status_code == 200:
                data = response.json()
                embedding = data.get("embedding", {}).get("values", [])
                return embedding if embedding else None
            elif response.status_code >= 500:
                last_error = f"Server {response.status_code}"
            else:
                print(f"⚠️ API error: {response.status_code} - {response.text[:100]}")
                return None

        except httpx.TimeoutException:
            last_error = "Timeout"
        except httpx.ConnectError as e:
            last_error = f"Connect: {e}"
        except Exception as e:
            last_error = str(e)

        if attempt < MAX_RETRIES:
            print(
                f"  ↻ Retry {attempt}/{MAX_RETRIES} after {backoff:.1f}s ({last_error})"
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    print(f"⚠️ Failed after {MAX_RETRIES} attempts: {last_error}")
    return None


def update_product_embedding(product_id: str, embedding: List[float]):
    supabase.table("products").update({"embedding": embedding}).eq(
        "id", product_id
    ).execute()


def main():
    print("\n🚀 Starting embedding generation (Google Gemini via Relay)...")

    # Get only products missing embeddings
    products = get_products(only_missing=True)
    total = len(products)

    if total == 0:
        print("✅ All products already have embeddings!")
        return

    print(f"Found {total} products without embeddings.\n")

    success = 0
    failed = 0

    for i, p in enumerate(products):
        name = p.get("name", "")
        category = p.get("category", "")

        # Prepare text (adds markers like "Prestige" for white pipes)
        text_to_embed = prepare_embedding_text(name, category)

        # Fallback if empty name
        if not text_to_embed:
            text_to_embed = f"{p['sku']} {name}"

        # Generate embedding via API
        embedding = generate_embedding(text_to_embed)

        if embedding:
            update_product_embedding(p["id"], embedding)
            success += 1
            if (i + 1) % 20 == 0 or (i + 1) == total:
                print(f"✓ [{i+1}/{total}] {name[:50]}...")
        else:
            failed += 1
            print(f"✗ [{i+1}/{total}] FAILED: {name[:50]}")

        # Rate limiting (be safe with relay)
        time.sleep(0.15)

    print(f"\n{'='*60}")
    print(f"✅ Done! Success: {success}, Failed: {failed}")
    print(f"   Total processed: {success + failed} / {total}")


if __name__ == "__main__":
    main()
