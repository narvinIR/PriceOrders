
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
