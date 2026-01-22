import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Extract connection details
SUPABASE_URL = os.getenv("SUPABASE_URL")
if not SUPABASE_URL:
    print("❌ SUPABASE_URL not found")
    exit(1)

# Extract project ref from URL (https://<ref>.supabase.co)
project_ref = urlparse(SUPABASE_URL).hostname.split(".")[0]

# Connection params
# Using Supavisor Pooler (IPv4 compatible)
# Region: Frankfurt (eu-central-1) based on GEMINI.md
DB_HOST = "aws-0-eu-central-1.pooler.supabase.com"
DB_NAME = "postgres"
# For pooler: user.project_ref
DB_USER = f"postgres.{project_ref}"
DB_PASS = os.getenv("SUPABASE_DB_PASSWORD")

if not DB_PASS:
    print("❌ SUPABASE_DB_PASSWORD not found")
    exit(1)

print(f"🔌 Connecting to {DB_HOST} (Pooler, Session Mode)...")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=5432,  # Session mode required for prepared statements/DDL
        sslmode="require",
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Read the SQL file
    # Ensure file exists
    if not os.path.exists("enable_vector.sql"):
        # Re-generate if missing (setup_pgvector.py creates it)
        print("⚠️ enable_vector.sql not found, creating setup...")
        from setup_pgvector import SQL_SETUP, SQL_MATCH_FUNCTION

        with open("enable_vector.sql", "w") as f:
            f.write(SQL_SETUP + "\n" + SQL_MATCH_FUNCTION)

    with open("enable_vector.sql", "r") as f:
        sql_script = f.read()

    print("🚀 Executing migration...")
    cur.execute(sql_script)

    print("✅ Migration applied successfully!")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    # Fallback to direct connection if pooler fails (unlikely if IPv6 blocked, but good to debug)
    print(
        f"DEBUG: Failed using {DB_HOST}. Original Host was db.{project_ref}.supabase.co"
    )
    exit(1)
