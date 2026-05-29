"""
MT5 Bridge - Direct connection to MetaTrader5 account
Handles: Account connection, portfolio updates, real-time data sync
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import time

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    HAS_MT5 = False
    logging.warning("MetaTrader5 not installed - mock mode will be used")

logger = logging.getLogger(__name__)


class MT5Bridge:
    """Direct bridge to MetaTrader5 terminal - handles all account operations"""

    def __init__(self, login: int, password: str, server: str, path: Optional[str] = None):
        """
        Initialize MT5 connection
        
        Args:
            login: MT5 account login (e.g., 405773)
            password: MT5 account password
            server: MT5 server name (e.g., "EquityEdge-Trade")
            path: Optional path to MT5 terminal (auto-detected if not provided)
        """
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.connected = False
        self.last_sync = None
        self.account_data_cache = {}
        self.connection_attempts = 0
        self.max_connection_attempts = 5

    def connect(self) -> bool:
        """
        Establish connection to MT5 terminal
        
        Returns:
            True if connected successfully, False otherwise
        """
        if not HAS_MT5:
            logger.error("MetaTrader5 not available - install with: pip install MetaTrader5")
            return False

        try:
            logger.info(f"🔗 Attempting to connect to MT5: {self.server}")

            # If path provided, use it; otherwise MT5 auto-detects
            if self.path:
                initialized = mt5.initialize(path=self.path)
            else:
                initialized = mt5.initialize()

            if not initialized:
                logger.error(f"❌ MT5 initialization failed: {mt5.last_error()}")
                self.connection_attempts += 1
                return False

            # Login to account
            authorized = mt5.login(login=self.login, password=self.password, server=self.server)

            if not authorized:
                logger.error(f"❌ MT5 login failed: {mt5.last_error()}")
                logger.error(f"   Verify: Login={self.login}, Server={self.server}")
                mt5.shutdown()
                self.connection_attempts += 1
                return False

            self.connected = True
            self.connection_attempts = 0
            logger.info(f"✅ Connected to MT5 - Account {self.login} on {self.server}")
            
            # Get initial account info
            account_info = mt5.account_info()
            if account_info:
                logger.info(f"   Balance: {account_info.balance:.2f} {account_info.currency}")
                logger.info(f"   Equity: {account_info.equity:.2f} {account_info.currency}")
            
            return True

        except Exception as e:
            logger.error(f"❌ Exception connecting to MT5: {e}")
            self.connection_attempts += 1
            return False

    def disconnect(self) -> None:
        """Gracefully disconnect from MT5"""
        try:
            if HAS_MT5:
                mt5.shutdown()
            self.connected = False
            logger.info("✅ Disconnected from MT5")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

    def get_account_info(self) -> Optional[Dict]:
        """
        Get current account information
        
        Returns:
            Dictionary with account data or None if failed
        """
        if not self.connected:
            return None

        try:
            account_info = mt5.account_info()
            
            if account_info is None:
                logger.warning("Failed to get account info from MT5")
                return None

            # Convert to dictionary
            data = {
                'login': account_info.login,
                'server': account_info.server,
                'balance': float(account_info.balance),
                'credit': float(account_info.credit),
                'profit': float(account_info.profit),
                'equity': float(account_info.equity),
                'margin': float(account_info.margin),
                'margin_free': float(account_info.margin_free),
                'margin_level': float(account_info.margin_level) if account_info.margin_level > 0 else 0,
                'currency': account_info.currency,
                'timestamp': datetime.now().isoformat(),
                'connection_status': 'CONNECTED'
            }

            self.account_data_cache = data
            self.last_sync = datetime.now()
            
            return data

        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """
        Get all open positions
        
        Returns:
            List of open positions
        """
        if not self.connected:
            return []

        try:
            positions = mt5.positions_get()
            
            if positions is None:
                return []

            position_list = []
            for pos in positions:
                position_list.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == 0 else 'SELL',
                    'volume': float(pos.volume),
                    'price_open': float(pos.price_open),
                    'price_current': float(pos.price_current),
                    'profit': float(pos.profit),
                    'commission': float(pos.commission) if hasattr(pos, 'commission') else 0.0,
                    'time_open': datetime.fromtimestamp(pos.time).isoformat(),
                    'swap': float(pos.swap) if hasattr(pos, 'swap') else 0,
                })

            return position_list

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_deal_history(self, days: int = 7) -> List[Dict]:
        """
        Get closed deals/trades from last N days
        
        Args:
            days: Number of days of history to retrieve
            
        Returns:
            List of closed deals
        """
        if not self.connected:
            return []

        try:
            from_date = datetime.now() - timedelta(days=days)
            deals = mt5.history_deals_get(from_date, datetime.now())
            
            if deals is None:
                return []

            deal_list = []
            for deal in deals:
                deal_list.append({
                    'ticket': deal.ticket,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == 0 else 'SELL',
                    'volume': float(deal.volume),
                    'price': float(deal.price),
                    'profit': float(deal.profit),
                    'commission': float(deal.commission),
                    'time': datetime.fromtimestamp(deal.time).isoformat(),
                    'comment': deal.comment if hasattr(deal, 'comment') else '',
                })

            return deal_list

        except Exception as e:
            logger.error(f"Error getting deal history: {e}")
            return []

    def get_orders(self) -> List[Dict]:
        """
        Get all pending orders
        
        Returns:
            List of pending orders
        """
        if not self.connected:
            return []

        try:
            orders = mt5.orders_get()
            
            if orders is None:
                return []

            order_list = []
            for order in orders:
                order_list.append({
                    'ticket': order.ticket,
                    'symbol': order.symbol,
                    'type': order.type,  # 0=BUY, 1=SELL, 2=BUY_LIMIT, etc.
                    'state': order.state,
                    'volume_initial': float(order.volume_initial),
                    'volume_current': float(order.volume_current),
                    'price_open': float(order.price_open),
                    'time_setup': datetime.fromtimestamp(order.time_setup).isoformat(),
                    'comment': order.comment if hasattr(order, 'comment') else '',
                })

            return order_list

        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []

    def get_symbol_price(self, symbol: str) -> Optional[Tuple[float, float]]:
        """
        Get current bid/ask price for symbol
        
        Args:
            symbol: Symbol name (e.g., 'EURUSD')
            
        Returns:
            Tuple of (bid, ask) or None if failed
        """
        if not self.connected:
            return None

        try:
            tick = mt5.symbol_info_tick(symbol)
            
            if tick is None:
                logger.warning(f"Failed to get tick for {symbol}")
                return None

            return (float(tick.bid), float(tick.ask))

        except Exception as e:
            logger.error(f"Error getting symbol price for {symbol}: {e}")
            return None

    def get_symbol_rates(self, symbol: str, timeframe: int = 1, count: int = 100) -> Optional[List[Dict]]:
        """
        Get OHLC rates for symbol
        
        Args:
            symbol: Symbol name (e.g., 'EURUSD')
            timeframe: Timeframe (1=M1, 5=M5, 15=M15, 60=H1, etc.)
            count: Number of bars to retrieve
            
        Returns:
            List of OHLC bars or None if failed
        """
        if not self.connected:
            return None

        try:
            # Map timeframe numbers to MT5 constants
            tf_map = {
                1: mt5.TIMEFRAME_M1,
                5: mt5.TIMEFRAME_M5,
                15: mt5.TIMEFRAME_M15,
                30: mt5.TIMEFRAME_M30,
                60: mt5.TIMEFRAME_H1,
                240: mt5.TIMEFRAME_H4,
                1440: mt5.TIMEFRAME_D1,
            }
            
            tf = tf_map.get(timeframe, mt5.TIMEFRAME_M5)
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            
            if rates is None:
                logger.warning(f"Failed to get rates for {symbol}")
                return None

            rate_list = []
            for rate in rates:
                rate_list.append({
                    'time': datetime.fromtimestamp(rate['time']).isoformat(),
                    'open': float(rate['open']),
                    'high': float(rate['high']),
                    'low': float(rate['low']),
                    'close': float(rate['close']),
                    'tick_volume': int(rate['tick_volume']),
                })

            return rate_list

        except Exception as e:
            logger.error(f"Error getting rates for {symbol}: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if currently connected to MT5"""
        if not HAS_MT5:
            return False
        
        try:
            # Try to get account info - if it works, we're connected
            account_info = mt5.account_info()
            return account_info is not None
        except:
            return False

    def get_connection_status(self) -> Dict:
        """Get detailed connection status"""
        return {
            'has_mt5': HAS_MT5,
            'connected': self.is_connected(),
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'connection_attempts': self.connection_attempts,
            'account_cached': bool(self.account_data_cache),
            'last_known_balance': self.account_data_cache.get('balance') if self.account_data_cache else None,
        }
