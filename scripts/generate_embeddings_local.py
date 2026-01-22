import os
import time
from typing import List

from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

from backend.utils.matching_helpers import prepare_embedding_text

# Load env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

# Init clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Init Model (Local)
print("📥 Loading local model (cointegrated/rubert-tiny2)...")
model = SentenceTransformer("cointegrated/rubert-tiny2")
# Note: rubert-tiny2 creates 312 dim embeddings.
# OpenAI used 1536 dim.
# We MUST update SQL/DB schema to 312 dim!


def get_products():
    """Fetch all products with category."""
    response = supabase.table("products").select("id, name, sku, category").execute()
    return response.data


def update_product_embedding(product_id: str, embedding: List[float]):
    supabase.table("products").update({"embedding": embedding}).eq(
        "id", product_id
    ).execute()


def main():
    print("🚀 Starting embedding generation (using local model)...")
    products = get_products()
    total = len(products)
    print(f"Found {total} products.")

    for i, p in enumerate(products):
        name = p.get("name", "")
        category = p.get("category", "")

        # Prepare text
        text_to_embed = prepare_embedding_text(name, category)

        # Fallback if empty name
        if not text_to_embed:
            text_to_embed = f"{p['sku']} {name}"

        # Generate embedding locally
        try:
            embedding = model.encode(text_to_embed).tolist()
            update_product_embedding(p["id"], embedding)

            if i % 20 == 0:
                print(f"[{i+1}/{total}] Processed: {name[:30]}...")

        except Exception as e:
            print(f"⚠️ Failed to embed: {name} ({e})")

    print("✅ Done!")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
