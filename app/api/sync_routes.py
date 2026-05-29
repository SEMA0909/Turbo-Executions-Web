"""
Real-Time Sync API Endpoints
Exposes MT5 data via REST API for frontend consumption
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from app.core.sync_service import SyncServiceManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["realtime-sync"])


@router.get("/status")
async def get_sync_status() -> Dict[str, Any]:
    """
    Get current sync service status
    
    Returns:
        {
            'running': bool,
            'connected': bool,
            'sync_count': int,
            'last_sync': str (ISO format),
            'current_balance': float,
            'current_equity': float,
            'open_positions': int,
            ...
        }
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(
            status_code=503,
            detail="Sync service not initialized"
        )
    
    return sync_service.get_status()


@router.get("/account")
async def get_account_info() -> Dict[str, Any]:
    """
    Get current account information
    
    Returns:
        {
            'login': int,
            'balance': float,
            'equity': float,
            'profit': float,
            'margin': float,
            'margin_free': float,
            'margin_level': float,
            'currency': str,
            'connection_status': str,
            'timestamp': str (ISO format)
        }
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    
    data = sync_service.get_current_data()
    
    if data is None or 'account' not in data:
        raise HTTPException(status_code=503, detail="No account data available")
    
    return data['account']


@router.get("/positions")
async def get_open_positions() -> Dict[str, Any]:
    """
    Get all open positions
    
    Returns:
        {
            'count': int,
            'positions': [
                {
                    'ticket': int,
                    'symbol': str,
                    'type': str ('BUY' or 'SELL'),
                    'volume': float,
                    'price_open': float,
                    'price_current': float,
                    'profit': float,
                    'time_open': str,
                    ...
                },
                ...
            ]
        }
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    
    data = sync_service.get_current_data()
    
    if data is None:
        raise HTTPException(status_code=503, detail="No data available")
    
    positions = data.get('positions', [])
    
    # Calculate statistics
    total_profit = sum(p['profit'] for p in positions)
    buy_positions = [p for p in positions if p['type'] == 'BUY']
    sell_positions = [p for p in positions if p['type'] == 'SELL']
    
    return {
        'count': len(positions),
        'buy_count': len(buy_positions),
        'sell_count': len(sell_positions),
        'total_profit': total_profit,
        'positions': positions,
        'timestamp': data.get('sync_timestamp')
    }


@router.get("/orders")
async def get_pending_orders() -> Dict[str, Any]:
    """
    Get all pending orders
    
    Returns:
        {
            'count': int,
            'orders': [
                {
                    'ticket': int,
                    'symbol': str,
                    'type': int,
                    'volume_current': float,
                    'price_open': float,
                    ...
                },
                ...
            ]
        }
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    
    data = sync_service.get_current_data()
    
    if data is None:
        raise HTTPException(status_code=503, detail="No data available")
    
    orders = data.get('orders', [])
    
    return {
        'count': len(orders),
        'orders': orders,
        'timestamp': data.get('sync_timestamp')
    }


@router.get("/deals")
async def get_deal_history() -> Dict[str, Any]:
    """
    Get closed deals/trade history (last 7 days)
    
    Returns:
        {
            'count': int,
            'total_profit': float,
            'deals': [
                {
                    'ticket': int,
                    'symbol': str,
                    'type': str,
                    'volume': float,
                    'price': float,
                    'profit': float,
                    'time': str,
                    ...
                },
                ...
            ]
        }
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    
    data = sync_service.get_current_data()
    
    if data is None:
        raise HTTPException(status_code=503, detail="No data available")
    
    deals = data.get('deals', [])
    total_profit = sum(d['profit'] for d in deals)
    winning_trades = len([d for d in deals if d['profit'] > 0])
    losing_trades = len([d for d in deals if d['profit'] < 0])
    
    return {
        'count': len(deals),
        'total_profit': total_profit,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': winning_trades / len(deals) * 100 if deals else 0,
        'deals': deals,
        'timestamp': data.get('sync_timestamp')
    }


@router.get("/portfolio")
async def get_full_portfolio() -> Dict[str, Any]:
    """
    Get complete portfolio snapshot (all data)
    
    Returns:
        {
            'account': {...},
            'positions': [...],
            'orders': [...],
            'deals': [...],
            'summary': {
                'total_profit': float,
                'open_positions': int,
                'pending_orders': int,
                'recent_trades': int,
                'portfolio_health': 'HEALTHY' | 'WARNING' | 'CRITICAL'
            },
            'sync_timestamp': str
        }
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    
    data = sync_service.get_current_data()
    
    if data is None:
        raise HTTPException(status_code=503, detail="No data available")
    
    account = data.get('account', {})
    positions = data.get('positions', [])
    orders = data.get('orders', [])
    deals = data.get('deals', [])
    
    # Calculate portfolio health
    total_profit = account.get('profit', 0)
    margin_level = account.get('margin_level', 0)
    
    if margin_level > 200:
        portfolio_health = 'HEALTHY'
    elif margin_level > 150:
        portfolio_health = 'WARNING'
    else:
        portfolio_health = 'CRITICAL'
    
    return {
        'account': account,
        'positions': positions,
        'orders': orders,
        'deals': deals,
        'summary': {
            'total_profit': total_profit,
            'open_positions': len(positions),
            'pending_orders': len(orders),
            'recent_trades': len(deals),
            'portfolio_health': portfolio_health,
            'margin_level': margin_level,
        },
        'sync_timestamp': data.get('sync_timestamp')
    }


@router.post("/connect")
async def trigger_sync_connection() -> Dict[str, str]:
    """
    Manually trigger a connection/sync attempt
    (Useful if connection was lost)
    
    Returns:
        {'status': 'connected'|'failed', 'message': str}
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    
    logger.info("Manual sync trigger requested")
    
    if sync_service.mt5_bridge.connect():
        sync_service.start()
        return {
            'status': 'connected',
            'message': 'Connected to MT5 and sync started'
        }
    else:
        return {
            'status': 'failed',
            'message': 'Failed to connect to MT5'
        }


@router.post("/disconnect")
async def stop_sync() -> Dict[str, str]:
    """
    Stop the sync service
    
    Returns:
        {'status': 'stopped', 'message': str}
    """
    sync_service = SyncServiceManager.get_instance()
    
    if sync_service is None:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    
    logger.info("Sync stop requested")
    sync_service.stop()
    
    return {
        'status': 'stopped',
        'message': 'Sync service stopped'
    }


@router.get("/webhook/netlify-ready")
async def netlify_webhook_ready() -> Dict[str, str]:
    """
    Webhook endpoint for Netlify to know backend is ready
    Add to Netlify Deploy settings for post-deploy notifications
    
    Returns:
        {'status': 'ready', 'backend': 'operational'}
    """
    sync_service = SyncServiceManager.get_instance()
    
    is_running = sync_service is not None and sync_service.running
    
    return {
        'status': 'ready' if is_running else 'initializing',
        'backend': 'operational',
        'sync_running': is_running
    }
