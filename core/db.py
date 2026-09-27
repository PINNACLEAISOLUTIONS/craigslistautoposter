import os
from pathlib import Path
from typing import Optional
import psycopg2
from dotenv import load_dotenv

# Load .env
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

DATABASE_URL = os.getenv("DATABASE_URL")

def log_post_to_neon(
    job_id: str,
    city: str,
    subdomain: str,
    title: str,
    post_url: Optional[str] = None,
    phone_used: Optional[str] = "904-686-6593",
    status: str = "published"
) -> bool:
    """Inserts or updates a Craigslist post record into Neon PostgreSQL."""
    if not DATABASE_URL:
        print("[Neon DB] No DATABASE_URL found. Skipping DB sync.")
        return False

    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS craigslist_posts (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(100) UNIQUE NOT NULL,
                    city VARCHAR(100) NOT NULL,
                    subdomain VARCHAR(100) NOT NULL,
                    title TEXT NOT NULL,
                    post_url TEXT,
                    phone_used VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'published',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                INSERT INTO craigslist_posts (job_id, city, subdomain, title, post_url, phone_used, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    post_url = EXCLUDED.post_url,
                    phone_used = EXCLUDED.phone_used,
                    created_at = CURRENT_TIMESTAMP;
            """, (job_id, city, subdomain, title, post_url or "", phone_used or "", status))
            conn.commit()
        conn.close()
        print(f"[Neon DB] Successfully recorded {job_id} ({city}) in Neon PostgreSQL.")
        return True
    except Exception as e:
        print(f"[Neon DB Error] Could not log to Neon: {e}")
        return False
