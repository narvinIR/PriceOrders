import os
import time
from typing import List

from dotenv import load_dotenv
from supabase import create_client, Client

from backend.utils.openai_client import generate_embedding
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


def get_products():
    """Fetch all products with category."""
    response = supabase.table("products").select("id, name, sku, category").execute()
    return response.data


def update_product_embedding(product_id: str, embedding: List[float]):
    supabase.table("products").update({"embedding": embedding}).eq(
        "id", product_id
    ).execute()


def main():
    print("🚀 Starting embedding generation (with category enhancement)...")
    products = get_products()
    total = len(products)
    print(f"Found {total} products.")

    for i, p in enumerate(products):
        name = p.get("name", "")
        category = p.get("category", "")
        # Prepare text using the logic with category enhancement
        text_to_embed = prepare_embedding_text(name, category)

        # Fallback if empty name?
        if not text_to_embed:
            # Maybe use raw name or sku?
            text_to_embed = f"{p['sku']} {name}"

        print(f"[{i+1}/{total}] Processing: {text_to_embed[:50]}...")

        embedding = generate_embedding(text_to_embed)
        if embedding:
            update_product_embedding(p["id"], embedding)
            time.sleep(0.05)  # Slight delay
        else:
            print(f"⚠️ Failed to embed: {name}")

    print("✅ Done!")


if __name__ == "__main__":
    main()
