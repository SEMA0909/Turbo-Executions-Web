# write_hooks.py
import logging
from .supabase_client import insert_signal, insert_snapshot, insert_trade
logger = logging.getLogger('supabase_hooks')


def publish_signal_if_valid(signal: dict, validator) -> bool:
    try:
        ok = validator(signal)
    except Exception:
        logger.exception('validator failed')
        return False
    if not ok:
        logger.debug('rejected %s', signal.get('symbol'))
        return False
    try:
        insert_signal(signal)
        logger.info('published signal %s', signal.get('symbol'))
        return True
    except Exception:
        logger.exception('publish failed')
        return False


def publish_snapshot(snapshot: dict) -> bool:
    try:
        insert_snapshot(snapshot)
        logger.info('snapshot published')
        return True
    except Exception:
        logger.exception('snapshot publish failed')
        return False


def publish_trade(trade: dict) -> bool:
    try:
        insert_trade(trade)
        logger.info('trade published')
        return True
    except Exception:
        logger.exception('trade publish failed')
        return False

# Example usage:
# from supabase_integration.backend.write_hooks import publish_signal_if_valid
# publish_signal_if_valid(signal, validator_function)