#!/usr/bin/env python3
"""
🚀 TURBO EXECUTIONS - LOCAL START SCRIPT
Automatically starts MT5 connection and real-time sync
Run this from terminal: python local_start.py
"""

import os
import sys
import logging
import asyncio
import signal
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows emoji encoding before any logging
if sys.platform == "win32":
    import io
    # Set UTF-8 encoding for stdout/stderr before logger
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Create handlers with proper encoding
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

file_handler = logging.FileHandler('data/local_sync.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[stdout_handler, file_handler]
)

logger = logging.getLogger(__name__)


def load_environment():
    """Load environment variables"""
    env_file = Path('.env')
    
    if not env_file.exists():
        logger.error("❌ .env file not found!")
        logger.error("   Create .env with MT5 credentials (see .env.example)")
        sys.exit(1)
    
    load_dotenv(env_file)
    
    # Get MT5 credentials
    mt5_login = os.getenv('MT5_LOGIN')
    mt5_password = os.getenv('MT5_PASSWORD')
    mt5_server = os.getenv('MT5_SERVER')
    mt5_path = os.getenv('MT5_PATH')
    poll_interval = int(os.getenv('POLL_INTERVAL_SECONDS', '5'))
    
    if not all([mt5_login, mt5_password, mt5_server]):
        logger.error("❌ Missing MT5 credentials in .env!")
        logger.error("   Required: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER")
        sys.exit(1)
    
    return {
        'login': int(mt5_login),
        'password': mt5_password,
        'server': mt5_server,
        'path': mt5_path,
        'poll_interval': poll_interval,
    }


def print_banner():
    """Print welcome banner"""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║        🚀 TURBO EXECUTIONS - LOCAL REAL-TIME SYNC 🚀            ║
║                                                                  ║
║  Your MT5 account is syncing with cloud in real-time!           ║
║  Portfolio updates visible on Netlify frontend instantly.       ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  📍 Local Backend: http://localhost:8000                        ║
║  🌐 Netlify Frontend: https://your-netlify-domain.netlify.app  ║
║  📊 Account Data: Syncing every 5 seconds                       ║
║  🔄 Supabase: Real-time updates enabled                         ║
║                                                                  ║
║  Press Ctrl+C to stop                                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """
    print(banner)


async def main():
    """Main entry point"""
    print_banner()
    
    # Load configuration
    logger.info("📋 Loading configuration from .env...")
    config = load_environment()
    
    logger.info(f"MT5 Account: {config['login']}")
    logger.info(f"MT5 Server: {config['server']}")
    logger.info(f"Poll Interval: {config['poll_interval']}s")
    
    # Import sync service
    try:
        from app.core.sync_service import SyncServiceManager
    except ImportError as e:
        logger.error(f"❌ Failed to import sync service: {e}")
        sys.exit(1)
    
    # Initialize sync service
    logger.info("🔄 Initializing real-time sync service...")
    sync_service = SyncServiceManager.initialize(
        mt5_login=config['login'],
        mt5_password=config['password'],
        mt5_server=config['server'],
        mt5_path=config['path'],
        poll_interval=config['poll_interval'],
    )
    
    # Connect to MT5
    if not sync_service.connect():
        logger.error("❌ Failed to connect to MT5!")
        logger.error("   Make sure:")
        logger.error("   1. MetaTrader5 is installed")
        logger.error("   2. MT5 terminal is open and logged in")
        logger.error("   3. Credentials in .env are correct")
        sys.exit(1)
    
    # Start background sync
    sync_service.start()
    logger.info(sync_service.get_formatted_status())
    
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        logger.info("\n⏹️ Shutting down...")
        sync_service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep running
    try:
        logger.info("✅ Real-time sync is now ACTIVE")
        logger.info("💡 Your portfolio is being synced to Netlify automatically")
        logger.info("")
        
        # Print status every 60 seconds
        counter = 0
        while True:
            await asyncio.sleep(1)
            counter += 1
            
            if counter >= 60:
                logger.info(sync_service.get_formatted_status())
                counter = 0
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Interrupted by user")
        sync_service.stop()


if __name__ == '__main__':
    asyncio.run(main())
