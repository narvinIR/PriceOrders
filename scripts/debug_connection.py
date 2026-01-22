import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
PROJECT_REF = "cyfmvsxqswbkazgckxbs"
# For pooler connection, user is postgres.<ref>
DB_USER = f"postgres.{PROJECT_REF}"

# Exhaustive list of Supavisor regions
REGIONS = [
    ("Frankfurt (EU Central 1)", "aws-0-eu-central-1.pooler.supabase.com"),
    ("Ireland (EU West 1)", "aws-0-eu-west-1.pooler.supabase.com"),
    ("London (EU West 2)", "aws-0-eu-west-2.pooler.supabase.com"),
    ("Paris (EU West 3)", "aws-0-eu-west-3.pooler.supabase.com"),
    ("Stockholm (EU North 1)", "aws-0-eu-north-1.pooler.supabase.com"),
    ("US East 1 (N. Virginia)", "aws-0-us-east-1.pooler.supabase.com"),
    ("US East 2 (Ohio)", "aws-0-us-east-2.pooler.supabase.com"),
    ("US West 1 (N. California)", "aws-0-us-west-1.pooler.supabase.com"),
    ("US West 2 (Oregon)", "aws-0-us-west-2.pooler.supabase.com"),
    ("Canada (Central)", "aws-0-ca-central-1.pooler.supabase.com"),
    ("Singapore (AP Southeast 1)", "aws-0-ap-southeast-1.pooler.supabase.com"),
    ("Sydney (AP Southeast 2)", "aws-0-ap-southeast-2.pooler.supabase.com"),
    ("Tokyo (AP Northeast 1)", "aws-0-ap-northeast-1.pooler.supabase.com"),
    ("Seoul (AP Northeast 2)", "aws-0-ap-northeast-2.pooler.supabase.com"),
    ("Mumbai (AP South 1)", "aws-0-ap-south-1.pooler.supabase.com"),
    ("Sao Paulo (SA East 1)", "aws-0-sa-east-1.pooler.supabase.com"),
]

print(f"🔍 Testing connection for project {PROJECT_REF}...")

# Check if password is set
if not PASSWORD:
    print("❌ SUPABASE_DB_PASSWORD not found in .env")
    exit(1)

for name, host in REGIONS:
    print(f"\nTrying {name} ({host})...")
    try:
        # Use port 6543 (Transaction Mode) which is usually open for poolers
        # Port 5432 (Session Mode) might also work
        conn = psycopg2.connect(
            host=host,
            database="postgres",
            user=DB_USER,
            password=PASSWORD,
            port=6543,
            connect_timeout=3,
            sslmode="require",
        )
        print(f"✅ SUCCESS! Connected to {name}")
        conn.close()
        exit(0)  # Found it!
    except psycopg2.OperationalError as e:
        err = str(e).strip()
        if "Network is unreachable" in err:
            print(f"❌ Network unreachable")
        elif "Tenant or user not found" in err:
            print(f"❌ Tenant not found")
        elif "password authentication failed" in err:
            print(f"✅ FOUND REGION: {name} (But password failed)")
            print("Please verify SUPABASE_DB_PASSWORD in .env")
            exit(0)
        else:
            print(f"❌ Connection Error: {err.splitlines()[0]}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

print("\n⚠️ Could not connect to any known region.")
