import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


# Load these specifically for the script if not in environment
url = os.environ.get("SUPABASE_URL")
# Try ANON key specifically as the service role key in env looks suspicious (sb_secret_...)
key = os.environ.get("SUPABASE_ANON_KEY")

print(f"Connecting to {url}...")
print(f"Using key starting with: {key[:10] if key else 'None'}...")

try:
    supabase: Client = create_client(url, key)
    # Just try to get server health or a simple read
    response = supabase.table('products').select('count', count='exact').limit(1).execute()
    print(f"Connection successful! Found products.")
except Exception as e:
    print(f"Connection failed: {e}")
