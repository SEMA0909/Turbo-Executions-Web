# supabase_client.py
from supabase import create_client
import os
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment')

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def insert_signal(signal: Dict[str, Any]):
    resp = sb.table('signals').insert(signal).execute()
    if resp.error:
        raise RuntimeError(resp.error.message)
    return resp.data


def insert_snapshot(snapshot: Dict[str, Any]):
    resp = sb.table('snapshots').insert(snapshot).execute()
    if resp.error:
        raise RuntimeError(resp.error.message)
    return resp.data


def insert_trade(trade: Dict[str, Any]):
    resp = sb.table('trades').insert(trade).execute()
    if resp.error:
        raise RuntimeError(resp.error.message)
    return resp.data
