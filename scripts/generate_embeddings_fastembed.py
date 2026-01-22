import os
import time
from typing import List

from dotenv import load_dotenv
from supabase import create_client, Client
from fastembed import TextEmbedding

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

# Init Model (FastEmbed)
print(
    "📥 Loading FastEmbed model (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)..."
)
model = TextEmbedding(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def get_products():
    """Fetch all products with category."""
    response = supabase.table("products").select("id, name, sku, category").execute()
    return response.data


def update_product_embedding(product_id: str, embedding: List[float]):
    supabase.table("products").update({"embedding": embedding}).eq(
        "id", product_id
    ).execute()


def main():
    print("🚀 Starting embedding generation (FastEmbed)...")
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
            # list(generate) gives list of vectors
            embeddings = list(model.embed([text_to_embed]))
            embedding = embeddings[0].tolist()

            update_product_embedding(p["id"], embedding)

            if i % 20 == 0:
                print(f"[{i+1}/{total}] Processed: {name[:30]}...")

        except Exception as e:
            print(f"⚠️ Failed to embed: {name} ({e})")

    print("✅ Done!")


if __name__ == "__main__":
    main()
