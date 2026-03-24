#!/usr/bin/env python3
"""
Run the GradConnectAI migration (lab_focus, opportunity_score, experience_snippet).
Uses SYNC_DATABASE_URL from config/app.env. No psql required.
"""
import os
import sys

from pathlib import Path

backend_dir = Path(__file__).resolve().parent
root_dir = backend_dir.parent
env_file = root_dir / "config" / "app.env"
env_local_file = root_dir / "config" / "app.local.env"


def _load_env_file(path: Path, *, overwrite_existing: bool) -> None:
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"")
                if overwrite_existing:
                    os.environ[key] = value
                else:
                    os.environ.setdefault(key, value)


_load_env_file(env_file, overwrite_existing=False)
_load_env_file(env_local_file, overwrite_existing=True)

url = os.environ.get("SYNC_DATABASE_URL")
if not url:
    print("Missing SYNC_DATABASE_URL in config/app.env", file=sys.stderr)
    sys.exit(1)
url = url.strip().strip("'\"")
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
