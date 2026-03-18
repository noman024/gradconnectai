#!/usr/bin/env python3
"""
Run the GradConnectAI database schema against the configured database.
Uses SYNC_DATABASE_URL (postgresql://...). Enables pgvector then runs schema.sql.
"""
import os
import sys

from pathlib import Path

backend_dir = Path(__file__).resolve().parent
root_dir = backend_dir.parent
env_file = root_dir / "config" / "app.env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"")
                os.environ.setdefault(key, value)

url = os.environ.get("SYNC_DATABASE_URL")
if not url:
    print("Missing SYNC_DATABASE_URL in config/app.env", file=sys.stderr)
    sys.exit(1)
url = url.strip().strip("'\"")
if not url.startswith("postgresql://") and not url.startswith("postgres://"):
    print("Invalid connection URL: must start with postgresql:// or postgres://", file=sys.stderr)
    print("Example (Supabase): postgresql://postgres.PROJECT_REF:YOUR_PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres", file=sys.stderr)
    print("Get the full URI from Supabase: Project Settings → Database → Connection string (URI).", file=sys.stderr)
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

schema_path = backend_dir / "app" / "db" / "schema.sql"
if not schema_path.exists():
    print(f"Schema file not found: {schema_path}", file=sys.stderr)
    sys.exit(1)

def main():
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("Extension vector: OK")
    except Exception as e:
        print(f"Warning: vector extension: {e}")
    with open(schema_path) as f:
        cur.execute(f.read())
    print("Schema applied successfully.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
