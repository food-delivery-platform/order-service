"""Thin Supabase wrapper (canonical order store). supabase imported lazily."""
from src.shared.config import env

_client = None

def get_client():
    global _client
    if _client is None:
        from supabase import create_client  # lazy import
        _client = create_client(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY)
    return _client
