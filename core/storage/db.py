"""Supabase client initialisation — single shared client for the application."""
import os

from supabase import Client, create_client


def get_client() -> Client:
    """Return an initialised Supabase client using env vars."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)
