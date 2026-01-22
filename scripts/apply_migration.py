"""
Apply pgvector migration directly via Supabase REST API.
Uses Service Role Key for admin access.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Read SQL file
with open("enable_vector.sql", "r") as f:
    sql_content = f.read()

print("🚀 Applying pgvector migration...")

# Execute via RPC (Supabase allows raw SQL via service role)
try:
    # Try using the pg_execute function if available
    result = supabase.rpc("pg_execute", {"query": sql_content}).execute()
    print(f"✅ Migration applied! Result: {result}")
except Exception as e:
    print(f"⚠️ RPC method failed: {e}")
    print("\n📋 Please execute this SQL manually in Supabase Dashboard:")
    print("https://supabase.com/dashboard/project/cyfmvsxqswbkazgckxbs/sql")
    print("\n" + "-" * 60)
    print(sql_content)
    print("-" * 60)
