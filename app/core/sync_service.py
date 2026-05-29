"""
Real-Time Sync Service - Synchronizes MT5 account data to Supabase
Runs continuously and updates Netlify frontend automatically
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import threading
from pathlib import Path

from app.core.mt5_bridge import MT5Bridge

logger = logging.getLogger(__name__)


class RealtimeSyncService:
    """
    Manages real-time synchronization between local MT5 and cloud (Supabase)
    
    Features:
    - Continuous account polling
    - Background thread execution
    - Automatic Netlify frontend updates
    - Graceful error recovery
    - Local data persistence
    """

    def __init__(
        self,
        mt5_login: int,
        mt5_password: str,
        mt5_server: str,
        mt5_path: Optional[str] = None,
        poll_interval: int = 5,
        enable_supabase: bool = True,
    ):
        """
        Initialize the real-time sync service
        
        Args:
            mt5_login: MT5 account login
            mt5_password: MT5 account password
            mt5_server: MT5 server name
            mt5_path: Optional path to MT5 terminal
            poll_interval: Seconds between data polls (default 5)
            enable_supabase: Enable Supabase sync (default True)
        """
        self.mt5_bridge = MT5Bridge(mt5_login, mt5_password, mt5_server, mt5_path)
        self.poll_interval = poll_interval
        self.enable_supabase = enable_supabase
        
        self.running = False
        self.thread = None
        self.sync_count = 0
        self.sync_errors = 0
        self.last_sync = None
        
        # Data cache for offline access
        self.data_cache_dir = Path('data/sync_cache')
        self.data_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to import Supabase if enabled
        self.supabase_client = None
        if enable_supabase:
            try:
                from supabase import create_client
                supabase_url = os.getenv('SUPABASE_URL')
                supabase_key = os.getenv('SUPABASE_KEY')
                
                if supabase_url and supabase_key:
                    self.supabase_client = create_client(supabase_url, supabase_key)
                    logger.info("✅ Supabase client initialized for real-time sync")
                else:
                    logger.warning("⚠️ Supabase credentials not found - using local cache only")
            except ImportError:
                logger.warning("⚠️ Supabase not installed - using local cache only")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize Supabase: {e}")

    def connect(self) -> bool:
        """
        Connect to MT5 account
        
        Returns:
            True if connection successful
        """
        logger.info("🔗 Connecting to MT5...")
        success = self.mt5_bridge.connect()
        
        if success:
            logger.info("✅ MT5 connection established")
            # Do initial sync
            self._sync_once()
        else:
            logger.error("❌ Failed to connect to MT5")
        
        return success

    def start(self) -> None:
        """Start the background sync service"""
        if self.running:
            logger.warning("Sync service already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        logger.info(f"🚀 Real-time sync service started (poll interval: {self.poll_interval}s)")

    def stop(self) -> None:
        """Stop the background sync service"""
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.mt5_bridge.disconnect()
        logger.info("⏹️ Real-time sync service stopped")

    def _sync_loop(self) -> None:
        """Main sync loop - runs continuously in background thread"""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                self._sync_once()
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                self.sync_errors += 1
                logger.error(f"Sync error #{self.sync_errors}: {e}")
                
                # Reconnect if too many errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning("🔄 Too many errors - attempting reconnection...")
                    if self.mt5_bridge.connect():
                        consecutive_errors = 0
            
            time.sleep(self.poll_interval)

    def _sync_once(self) -> None:
        """Perform one sync cycle"""
        if not self.mt5_bridge.is_connected():
            logger.warning("⚠️ MT5 not connected - attempting reconnection...")
            if not self.mt5_bridge.connect():
                return

        # Get fresh data
        account_info = self.mt5_bridge.get_account_info()
        positions = self.mt5_bridge.get_positions()
        orders = self.mt5_bridge.get_orders()
        deal_history = self.mt5_bridge.get_deal_history(days=7)

        if account_info is None:
            logger.warning("Failed to get account info")
            return

        # Prepare sync payload
        payload = {
            'account': account_info,
            'positions': positions,
            'orders': orders,
            'deals': deal_history,
            'sync_timestamp': datetime.now().isoformat(),
            'sync_count': self.sync_count,
        }

        # Save to local cache
        self._save_cache(payload)

        # Push to Supabase if available
        if self.supabase_client:
            self._push_to_supabase(payload)

        # Push to Netlify (via function trigger)
        self._trigger_netlify_update(payload)

        self.sync_count += 1
        self.last_sync = datetime.now()

        if self.sync_count % 12 == 0:  # Log every minute (12 x 5s)
            logger.info(
                f"📊 Sync #{self.sync_count}: "
                f"Balance {account_info['balance']:.2f} | "
                f"Positions: {len(positions)} | "
                f"Profit: {account_info['profit']:+.2f}"
            )

    def _save_cache(self, data: Dict) -> None:
        """Save data to local cache for offline access"""
        try:
            cache_file = self.data_cache_dir / 'latest.json'
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def _push_to_supabase(self, data: Dict) -> None:
        """Push account data to Supabase real-time database"""
        if not self.supabase_client:
            return

        try:
            account_login = data['account']['login']
            
            # Update or insert account record
            self.supabase_client.table('account_sync').upsert({
                'account_id': account_login,
                'balance': data['account']['balance'],
                'equity': data['account']['equity'],
                'profit': data['account']['profit'],
                'margin_level': data['account']['margin_level'],
                'data': json.dumps(data),
                'updated_at': data['sync_timestamp'],
            }).execute()

            # Update positions in separate table
            positions_table = self.supabase_client.table('positions')
            
            # Clear old positions
            positions_table.delete().eq('account_id', account_login).execute()
            
            # Insert new positions
            if data['positions']:
                positions_table.insert([
                    {
                        'account_id': account_login,
                        **pos,
                        'updated_at': data['sync_timestamp'],
                    }
                    for pos in data['positions']
                ]).execute()

        except Exception as e:
            logger.warning(f"⚠️ Supabase sync failed: {e}")

    def _trigger_netlify_update(self, data: Dict) -> None:
        """
        Trigger Netlify function to update frontend in real-time
        
        Can be:
        1. Direct API call to Netlify function
        2. Webhook POST to your frontend
        3. WebSocket push to connected clients
        """
        try:
            # Method 1: POST to local frontend during development
            import requests
            
            # Update local frontend (if running)
            try:
                requests.post(
                    'http://localhost:3000/api/sync',
                    json=data,
                    timeout=2
                )
            except:
                pass  # Frontend may not be running locally
            
            # Method 2: Trigger Netlify build hook (optional)
            netlify_hook = os.getenv('NETLIFY_BUILD_HOOK')
            if netlify_hook:
                try:
                    requests.post(netlify_hook, timeout=5)
                except:
                    pass  # Build hook is optional

        except Exception as e:
            logger.debug(f"Could not trigger frontend update: {e}")

    def get_current_data(self) -> Optional[Dict]:
        """Get most recent synced data"""
        try:
            cache_file = self.data_cache_dir / 'latest.json'
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
        
        return None

    def get_status(self) -> Dict:
        """Get service status"""
        current_data = self.get_current_data()
        
        return {
            'running': self.running,
            'connected': self.mt5_bridge.is_connected(),
            'sync_count': self.sync_count,
            'sync_errors': self.sync_errors,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'poll_interval': self.poll_interval,
            'supabase_enabled': self.enable_supabase and self.supabase_client is not None,
            'current_balance': current_data['account']['balance'] if current_data else None,
            'current_equity': current_data['account']['equity'] if current_data else None,
            'open_positions': len(current_data['positions']) if current_data else 0,
        }

    def get_formatted_status(self) -> str:
        """Get human-readable status"""
        status = self.get_status()
        
        return f"""
╔════════════════════════════════════════════╗
║  📊 REAL-TIME SYNC SERVICE STATUS          ║
╠════════════════════════════════════════════╣
║  Status: {'🟢 RUNNING' if status['running'] else '🔴 STOPPED'}
║  MT5 Connection: {'🟢 CONNECTED' if status['connected'] else '🔴 DISCONNECTED'}
║  Syncs Completed: {status['sync_count']}
║  Errors: {status['sync_errors']}
║  Last Sync: {status['last_sync'] or 'Never'}
║  Poll Interval: {status['poll_interval']}s
║  Supabase: {'🟢 ENABLED' if status['supabase_enabled'] else '🔴 DISABLED'}
╠════════════════════════════════════════════╣
║  💰 Current Balance: {status['current_balance'] if status['current_balance'] else 'N/A'}
║  📈 Current Equity: {status['current_equity'] if status['current_equity'] else 'N/A'}
║  📍 Open Positions: {status['open_positions']}
╚════════════════════════════════════════════╝
"""


class SyncServiceManager:
    """Global singleton for managing the sync service"""
    
    _instance: Optional[RealtimeSyncService] = None

    @classmethod
    def get_instance(cls) -> Optional[RealtimeSyncService]:
        """Get the singleton instance"""
        return cls._instance

    @classmethod
    def initialize(
        cls,
        mt5_login: int,
        mt5_password: str,
        mt5_server: str,
        mt5_path: Optional[str] = None,
        poll_interval: int = 5,
    ) -> RealtimeSyncService:
        """Initialize and start the sync service"""
        if cls._instance is not None:
            logger.warning("Sync service already initialized")
            return cls._instance

        cls._instance = RealtimeSyncService(
            mt5_login=mt5_login,
            mt5_password=mt5_password,
            mt5_server=mt5_server,
            mt5_path=mt5_path,
            poll_interval=poll_interval,
        )
        
        return cls._instance

    @classmethod
    def start(cls) -> None:
        """Start the sync service"""
        if cls._instance:
            cls._instance.start()

    @classmethod
    def stop(cls) -> None:
        """Stop the sync service"""
        if cls._instance:
            cls._instance.stop()
