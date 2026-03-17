#!/usr/bin/env python3
"""
Run the GradConnectAI migration (lab_focus, opportunity_score, experience_snippet).
Uses SYNC_DATABASE_URL from .env. No psql required.
"""
import os
import sys

from pathlib import Path

backend_dir = Path(__file__).resolve().parent
env_file = backend_dir / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"")
                os.environ.setdefault(key, value)

url = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not url:
    print("Missing SYNC_DATABASE_URL or DATABASE_URL in .env", file=sys.stderr)
    sys.exit(1)
url = url.strip().strip("'\"")
if "+asyncpg" in url:
    url = url.replace("+asyncpg", "")
if not url.startswith("postgresql://") and not url.startswith("postgres://"):
    print("Invalid connection URL: must start with postgresql:// or postgres://", file=sys.stderr)
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

migrate_path = backend_dir / "migrate_add_lab_focus.sql"
if not migrate_path.exists():
    print(f"Migration file not found: {migrate_path}", file=sys.stderr)
    sys.exit(1)


def main():
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        with open(migrate_path) as f:
            cur.execute(f.read())
        print("Migration applied successfully.")
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
