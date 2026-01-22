import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in env")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SQL_SETUP = """
-- Enable pgvector extension
create extension if not exists vector;

-- Add embedding column to products table if not exists
do $$
begin
    if not exists (select 1 from information_schema.columns where table_name = 'products' and column_name = 'embedding') then
        alter table products add column embedding vector(1536);
    end if;
end $$;

-- Create index for faster search (HNSW)
create index if not exists products_embedding_idx on products using hnsw (embedding vector_cosine_ops);
"""

SQL_MATCH_FUNCTION = """
-- Create match_products function
create or replace function match_products (
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  sku text,
  name text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    products.id,
    products.product_code as sku, -- Assuming product_code is the column name for SKU
    products.name,
    1 - (products.embedding <=> query_embedding) as similarity
  from products
  where 1 - (products.embedding <=> query_embedding) > match_threshold
  order by products.embedding <=> query_embedding
  limit match_count;
end;
$$;
"""


def run_migration():
    print(f"Connecting to Supabase: {SUPABASE_URL}")

    # 1. Setup Extension and Table
    print("Enabling pgvector and adding column...")
    try:
        # Supabase-py doesn't support raw SQL directly on client usually,
        # but modern versions might.
        # If not, we use postgrest rpc if we had a function, but we are creating functions.
        # However, supabase-py client usually wraps postgrest.
        # Admin capabilities might be limited via standard client unless we use `rpc` to call a predefined sql-exec function
        # OR if we have direct postgres access.
        # But wait, `backend/models/database.py` might give a hint.
        # If we can't run raw SQL via client, we might need `postgres` connection string.
        # Let's try `rpc` if there is a 'exec_sql' function, or just use `supabase.postgrest.rpc(...)`?
        # No, usually we can't create extensions via client API unless mapped.

        # Let's assume we can use `supabase.rpc` IF there is a function. But we want to CREATE functions.
        # Most Supabase setups for management allow SQL execution via Dashboard.
        # FROM LOCAL SCRIPT:
        # If we don't have direct SQL access, we might be stuck.
        # BUT many Supabase projects have a helper function `exec_sql` or similar if setup.

        # Alternative: Use `sqlalchemy` or `psycopg2` if we have the connection string (postgres://...).
        # `SUPABASE_URL` is https...
        # DO parameters typically allow constructing the postgres URI:
        # postgres://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
        # The password is usually NOT in .env, only the SERVICE_KEY.

        # NOTE: If we cannot execute SQL, we have to ask the user to run it in Supabase Dashboard.
        # Let's try to check if there is an existing way in the project.
        # `scripts/verify_supabase.py` might show how they interact.

        pass
    except Exception as e:
        print(f"Error: {e}")

    # For now, let's output the SQL to a file so the user can run it,
    # OR we try to see if `scripts` folder implies we can run things.
    # The user manual `CLAUDE.md` mentions `supabase-unify` MCP for SQL, but that's for Unify.

    with open("enable_vector.sql", "w") as f:
        f.write(SQL_SETUP + "\n" + SQL_MATCH_FUNCTION)
    print("Saved SQL to enable_vector.sql. Please run this in Supabase SQL Editor.")


if __name__ == "__main__":
    run_migration()
