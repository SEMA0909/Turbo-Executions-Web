# 🚀 LOCAL REAL-TIME SETUP GUIDE

## Your Complete Local-to-Cloud Trading Platform

This guide will help you set up the complete real-time synchronization system that connects your local MT5 account directly to your Netlify frontend with zero lag.

---

## ⚙️ PREREQUISITES

Make sure you have:
- ✅ MetaTrader5 installed and running on Windows
- ✅ Your MT5 account logged in on your local machine
- ✅ VS Code terminal access
- ✅ Your MT5 login credentials (account number, password, server)
- ✅ Internet connection

---

## 🔧 SETUP STEPS (5-10 Minutes)

### Step 1: Fix Your `.env` File

Open `.env` in the root directory and make sure it looks like this:

```bash
# ✅ MUST be exactly your MT5 credentials (not mock values)
MT5_LOGIN="405773"
MT5_PASSWORD="N8odc?1bVD"
MT5_SERVER="EquityEdge-Trade"

# ✅ CRITICAL: Disable mock mode to use real MT5
MOCK_MODE=0

# ✅ Real-time sync settings
POLL_INTERVAL_SECONDS=5

# Other settings
INITIAL_BALANCE=2500
DAILY_DD_LIMIT_PCT=2
TOTAL_DD_LIMIT_PCT=5
PROFIT_TARGET_PCT=12

# Optional: Telegram alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Optional: Supabase (for cloud sync)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
```

**⚠️ IMPORTANT CHECKS:**
- `MOCK_MODE=0` (NOT 1!) - This activates real MT5 connection
- `MT5_LOGIN` - Should be numeric (e.g., 405773)
- `MT5_PASSWORD` - Should be your actual MT5 password
- `MT5_SERVER` - Should match your broker's server name exactly

### Step 2: Install/Update Dependencies

```bash
# Make sure you're in the project directory
cd C:\Users\Admin\Downloads\mt5-intel\mt5-intel

# Install required packages
pip install -r requirements.txt

# Specifically ensure these are installed:
pip install python-dotenv MetaTrader5 supabase uvicorn fastapi
```

### Step 3: Configure Supabase (Optional but Recommended)

To enable cloud sync to your Netlify frontend:

1. Go to [supabase.com](https://supabase.com)
2. Create/select your project
3. Get your API URL and Key from Settings → API
4. Add to `.env`:
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=your_anon_key
   ```

### Step 4: Start the Backend

**Method A: Terminal Mode** (See live updates)
```bash
python local_start.py
```

This will show:
```
╔══════════════════════════════════════════════════════════════════╗
║        🚀 TURBO EXECUTIONS - LOCAL REAL-TIME SYNC 🚀            ║
║                                                                  ║
║  📍 Local Backend: http://localhost:8000                        ║
║  🌐 Netlify Frontend: https://your-domain.netlify.app          ║
║  📊 Account Data: Syncing every 5 seconds                       ║
║  🔄 Supabase: Real-time updates enabled                         ║
╚══════════════════════════════════════════════════════════════════╝

✅ Real-time sync is now ACTIVE
💡 Your portfolio is being synced to Netlify automatically
```

**Method B: Backend + Frontend Mode** (In another terminal)
```bash
# Terminal 1: Start backend
python -m app.main

# Terminal 2: Start frontend
cd app/web
npm start
```

### Step 5: Verify Connection

Check if it's working by opening:
```
http://localhost:8000/api/sync/status
```

You should see JSON with `"connected": true` and your account balance.

---

## 🔄 HOW IT WORKS

### Real-Time Data Flow

```
Your MT5 Terminal (Windows)
        ↓
   [local_start.py or app/main.py]
        ↓
  MT5Bridge (connects via MT5.dll)
        ↓
  RealtimeSyncService (polls every 5 seconds)
        ↓
   Account Data Cache (data/sync_cache/latest.json)
        ↓
   ├─→ Supabase (Cloud database)
   │      ↓
   │   Your Netlify Frontend
   │   (Auto-updates when data changes)
   │
   └─→ API Endpoints (/api/sync/*)
        ↓
        Your custom frontend/dashboard
```

### What Gets Synced

**Every 5 seconds:**
- ✅ Account balance & equity
- ✅ Open positions (live P&L)
- ✅ Pending orders
- ✅ Recent closed trades
- ✅ Margin level & risk metrics

---

## 📊 USING THE DATA

### Option 1: Direct API Calls (Frontend)

```javascript
// Get current account info
fetch('http://localhost:8000/api/sync/account')
  .then(r => r.json())
  .then(data => {
    console.log('Balance:', data.balance);
    console.log('Equity:', data.equity);
  });

// Get open positions
fetch('http://localhost:8000/api/sync/positions')
  .then(r => r.json())
  .then(data => {
    console.log('Open Positions:', data.positions);
    console.log('Total P&L:', data.total_profit);
  });

// Get full portfolio
fetch('http://localhost:8000/api/sync/portfolio')
  .then(r => r.json())
  .then(data => {
    console.log('Portfolio:', data);
  });
```

### Option 2: Supabase Real-Time (React/Vue)

```javascript
import { supabase } from '@/supabaseClient';

// Subscribe to account updates
const subscription = supabase
  .from('account_sync')
  .on('*', payload => {
    console.log('Account updated:', payload.new);
    setBalance(payload.new.balance);
    setEquity(payload.new.equity);
  })
  .subscribe();

// Don't forget to unsubscribe
return () => subscription.unsubscribe();
```

### Option 3: WebSocket (Real-time Stream)

```javascript
// Connect to WebSocket stream
const ws = new WebSocket('ws://localhost:8000/ws?token=YOUR_TOKEN');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Real-time update:', data);
  updateDashboard(data);
};
```

---

## 🐛 TROUBLESHOOTING

### Problem: "Still showing mock_mode"
**Solution:**
```bash
# Check .env
cat .env | grep MOCK_MODE
# Should show: MOCK_MODE=0

# If it shows MOCK_MODE=1, change it to 0
```

### Problem: "Connection refused" or "Cannot connect to MT5"
**Solution:**
1. Make sure MT5 terminal is running on your machine
2. Make sure you're logged into your MT5 account
3. Check credentials in `.env` match exactly:
   ```bash
   # In MT5, go to Help → About
   # Copy your Account and Server name
   ```

### Problem: "Port 8000 already in use"
**Solution:**
```bash
# Find what's using port 8000
lsof -i :8000

# Or use a different port in .env
PORT=8001
```

### Problem: "MetaTrader5 module not found"
**Solution:**
```bash
# Install MetaTrader5
pip install MetaTrader5 --upgrade

# Verify installation
python -c "import MetaTrader5; print('✅ MT5 installed')"
```

### Problem: "Supabase connection failed"
**Solution:**
It's optional! The system works without it:
- ✅ Data is cached locally
- ✅ Frontend still updates via local API
- Remove or comment out SUPABASE_* variables

---

## 📱 ACCESSING FROM ANYWHERE

### Your Netlify Frontend
The website automatically updates because:
1. Local backend polls MT5 every 5 seconds
2. Data is stored in Supabase
3. Your Netlify frontend subscribes to Supabase changes
4. When data changes, frontend auto-updates instantly

**Access from anywhere:**
```
https://your-project.netlify.app
```

No need to keep your PC on! Well, sort of...

---

## 🎯 TO RUN INDEPENDENTLY (Background Service)

### On Windows: Task Scheduler

```batch
# Create run_bg.bat in project root
@echo off
cd C:\Users\Admin\Downloads\mt5-intel\mt5-intel
python local_start.py
```

Then:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: At startup / Every hour
4. Set action: Run run_bg.bat
5. Check "Run with highest privileges"

### On Windows: Windows Service

```bash
# Install as service
pip install pywin32
python -m pywin32_postinstall -install

# Create service (PowerShell as Admin)
New-Service -Name TurboSync -BinaryPathName "python C:\...\local_start.py" -DisplayName "Turbo Sync Service"

# Start service
Start-Service -Name TurboSync
```

### On Mac/Linux: Background Daemon

```bash
# Create turbo_sync.service
sudo nano /etc/systemd/system/turbo_sync.service
```

```ini
[Unit]
Description=Turbo Executions MT5 Sync Service
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 /path/to/local_start.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable turbo_sync
sudo systemctl start turbo_sync
```

---

## ✨ WHAT'S HAPPENING NOW

### When You Run `python local_start.py`:

1. **🔗 Connects to MT5**
   - Reads credentials from `.env`
   - Logs into your account
   - Gets account info

2. **📊 Starts Polling** (every 5 seconds)
   - Gets current balance & equity
   - Fetches open positions
   - Checks pending orders
   - Retrieves recent closed trades

3. **💾 Caches Data**
   - Saves to `data/sync_cache/latest.json`
   - Available offline

4. **☁️ Syncs to Cloud**
   - Pushes to Supabase (if configured)
   - Netlify frontend auto-updates
   - WebSocket clients receive live updates

5. **📱 Exposes APIs**
   - `/api/sync/account` - Account info
   - `/api/sync/positions` - Open trades
   - `/api/sync/portfolio` - Full snapshot
   - `/api/sync/status` - Service status

---

## 🎓 NEXT STEPS

### Short Term (This Week)
- [x] Set up `.env` with real credentials
- [x] Run `python local_start.py`
- [x] Verify connection with `/api/sync/status`
- [ ] Update Netlify frontend to use `/api/sync/*` endpoints
- [ ] Test real-time updates

### Medium Term (This Month)
- [ ] Configure Supabase for true cloud sync
- [ ] Set up background service (Task Scheduler)
- [ ] Add more metrics/dashboard updates
- [ ] Test access from mobile/other device

### Long Term (Ongoing)
- [ ] Monitor performance
- [ ] Add advanced visualizations
- [ ] Integrate trading signals
- [ ] Set up alerts and notifications

---

## 📞 SUPPORT

### Quick Tests

```bash
# Test 1: Check .env is correct
python -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('.env')); import os; print(f'Login: {os.getenv(\"MT5_LOGIN\")}'); print(f'Server: {os.getenv(\"MT5_SERVER\")}'); print(f'Mock Mode: {os.getenv(\"MOCK_MODE\")}')"

# Test 2: Check MT5 connection
python -c "import MetaTrader5 as mt5; print('MT5 available:', mt5.initialize())"

# Test 3: Check API is running
curl http://localhost:8000/api/health

# Test 4: Check sync status
curl http://localhost:8000/api/sync/status
```

### Manual Test of Full Flow

```python
# File: test_connection.py
import os
from dotenv import load_dotenv
from app.core.mt5_bridge import MT5Bridge

load_dotenv()

bridge = MT5Bridge(
    login=int(os.getenv('MT5_LOGIN')),
    password=os.getenv('MT5_PASSWORD'),
    server=os.getenv('MT5_SERVER'),
)

if bridge.connect():
    account = bridge.get_account_info()
    print(f"✅ Connected!")
    print(f"Balance: {account['balance']}")
    print(f"Equity: {account['equity']}")
    print(f"Positions: {len(bridge.get_positions())}")
    bridge.disconnect()
else:
    print("❌ Connection failed")
```

```bash
python test_connection.py
```

---

## 🎉 SUCCESS CHECKLIST

When everything is working, you should see:

- [x] `python local_start.py` runs without errors
- [x] Shows "✅ Connected to MT5"
- [x] Shows "✅ Real-time sync is now ACTIVE"
- [x] `http://localhost:8000/api/sync/status` returns JSON
- [x] JSON shows `"connected": true`
- [x] JSON shows your real balance (not mock)
- [x] Every 5 seconds, sync counter increments
- [x] Netlify frontend updates automatically
- [x] Can access portfolio from any device

---

## 🚀 YOU'RE ALL SET!

Your Turbo Executions platform is now:
✅ **Live** - MT5 connected and streaming
✅ **Real-time** - Updates every 5 seconds
✅ **Scalable** - Runs independently
✅ **Global** - Access from anywhere

Enjoy! 🎉

---

**Questions?** Check `app/core/sync_service.py` for the sync engine or `app/core/mt5_bridge.py` for MT5 connection details.

**Happy Trading!** 📈
