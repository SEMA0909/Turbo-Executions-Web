# 🎯 QUICK START - 5 MINUTES TO LIVE TRADING

## THE MISSION: Local MT5 → Real-Time Cloud Updates → Netlify

You want:
- ✅ Real MT5 data streaming from your PC
- ✅ Automatic updates on Netlify frontend
- ✅ Access portfolio anywhere
- ✅ No more mock mode!

**Here's how to do it RIGHT NOW:**

---

## ⚡ 5-MINUTE SETUP

### Step 1: Verify .env (1 minute)

Open `.env` file and make ABSOLUTELY SURE:

```bash
# THIS MUST BE 0 (not 1!) to enable real MT5
MOCK_MODE=0

# YOUR REAL MT5 CREDENTIALS
MT5_LOGIN=405773
MT5_PASSWORD=N8odc?1bVD
MT5_SERVER=EquityEdge-Trade
```

**❌ If you see MOCK_MODE=1** → Change to 0  
**❌ If you see MOCK_MODE="" or blank** → Set to 0

### Step 2: Start the Backend (2 minutes)

Open VS Code terminal and run:

```bash
python local_start.py
```

**✅ YOU SHOULD SEE:**

```
╔══════════════════════════════════════════════════════════════════╗
║        🚀 TURBO EXECUTIONS - LOCAL REAL-TIME SYNC 🚀            ║
║                                                                  ║
║  📍 Local Backend: http://localhost:8000                        ║
║  🌐 Netlify Frontend: https://your-netlify-domain.netlify.app  ║
║  📊 Account Data: Syncing every 5 seconds                       ║
║  🔄 Supabase: Real-time updates enabled                         ║
╚══════════════════════════════════════════════════════════════════╝

✅ Connected to MT5 - Account 405773 on EquityEdge-Trade
   Balance: 2500.00 USD
   Equity: 2500.00 USD
✅ Real-time sync is now ACTIVE
💡 Your portfolio is being synced to Netlify automatically
```

### Step 3: Test the Connection (1 minute)

Open browser and visit:
```
http://localhost:8000/api/sync/status
```

**✅ YOU SHOULD SEE:**
```json
{
  "running": true,
  "connected": true,
  "sync_count": 12,
  "current_balance": 2500.00,
  "current_equity": 2500.00,
  "open_positions": 0,
  "last_sync": "2024-05-29T14:10:44.123456"
}
```

### Step 4: Update Netlify Frontend (1 minute)

Your Netlify frontend should now be calling this endpoint instead of mock data.

**Update your frontend code:**

```javascript
// Before (mock mode):
const data = mockPortfolioData;

// After (real-time):
const response = await fetch('http://YOUR-BACKEND-URL/api/sync/portfolio');
const data = await response.json();
```

Or if using Supabase:

```javascript
// Subscribe to real-time updates
supabase
  .from('account_sync')
  .on('*', payload => {
    setBalance(payload.new.balance);
    setEquity(payload.new.equity);
    setPositions(payload.new.data.positions);
  })
  .subscribe();
```

---

## 🎉 THAT'S IT!

Your system is now:

```
🖥️ Local Terminal
   ↓ (MT5Bridge connects to your account)
📊 Real Data Streaming
   ↓ (every 5 seconds)
☁️ Supabase Cloud
   ↓ (real-time sync)
🌐 Netlify Frontend
   ↓ (instant updates)
📱 Your Portfolio Anywhere
```

---

## ❓ "STILL SHOWING MOCK MODE?"

### Diagnosis

Check what's happening:

```bash
# Check if MOCK_MODE is really 0
grep MOCK_MODE .env

# Check if sync service is running
curl http://localhost:8000/api/sync/status

# Check if MT5 is connected
curl http://localhost:8000/api/sync/account
```

### Common Fixes

| Problem | Solution |
|---------|----------|
| MOCK_MODE still shows 1 | Change to 0 in `.env` then restart |
| "Connection refused" | Make sure MT5 terminal is open on your PC |
| "Login failed" | Check credentials in `.env` match MT5 exactly |
| "Port 8000 in use" | Run on different port: `PORT=8001 python local_start.py` |
| "No module MetaTrader5" | Install: `pip install MetaTrader5` |

---

## 📊 AVAILABLE ENDPOINTS

Once running, these endpoints have REAL data:

### Account Information
```bash
curl http://localhost:8000/api/sync/account
```

### Open Positions
```bash
curl http://localhost:8000/api/sync/positions
```

### Pending Orders
```bash
curl http://localhost:8000/api/sync/orders
```

### Trade History
```bash
curl http://localhost:8000/api/sync/deals
```

### Full Portfolio
```bash
curl http://localhost:8000/api/sync/portfolio
```

### Service Status
```bash
curl http://localhost:8000/api/sync/status
```

---

## 🔄 HOW REAL-TIME WORKS

1. **Every 5 seconds:**
   - Local script polls your MT5 terminal
   - Gets current balance, positions, orders, trades
   - Updates local cache file

2. **Simultaneously:**
   - Pushes to Supabase (if configured)
   - Exposesdata via REST API

3. **Your Netlify Frontend:**
   - Calls `/api/sync/portfolio` every 5 seconds
   - OR subscribes to Supabase real-time updates
   - Auto-updates when data changes
   - No refresh needed!

---

## ✨ BONUS FEATURES

### Run as Background Service (Windows)

Create `run_bg.bat`:
```batch
@echo off
cd /d C:\Users\Admin\Downloads\mt5-intel\mt5-intel
python local_start.py
```

Then use Task Scheduler to run it on startup.

### Run on Render (Keep it running 24/7)

```bash
git push origin main
# Render auto-deploys and keeps backend running
```

### Run on Linux/Mac

```bash
nohup python local_start.py > sync.log 2>&1 &
```

---

## 🎓 YOUR FRONTEND EXAMPLES

### React
```jsx
import { useEffect, useState } from 'react';

export function Portfolio() {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/sync/portfolio');
        const data = await res.json();
        setPortfolio(data);
      } catch (err) {
        console.error('Failed to fetch portfolio:', err);
      } finally {
        setLoading(false);
      }
    };

    // Fetch immediately
    fetchData();

    // Then every 5 seconds
    const interval = setInterval(fetchData, 5000);

    return () => clearInterval(interval);
  }, []);

  if (loading) return <div>Loading...</div>;
  if (!portfolio) return <div>No data</div>;

  return (
    <div>
      <h2>Portfolio</h2>
      <p>Balance: ${portfolio.account.balance.toFixed(2)}</p>
      <p>Equity: ${portfolio.account.equity.toFixed(2)}</p>
      <p>Positions: {portfolio.summary.open_positions}</p>
      <p>Profit: ${portfolio.summary.total_profit.toFixed(2)}</p>
    </div>
  );
}
```

### Vue
```vue
<template>
  <div>
    <h2>Portfolio</h2>
    <p v-if="portfolio">
      Balance: ${{ portfolio.account.balance.toFixed(2) }}
    </p>
    <p v-if="portfolio">
      Equity: ${{ portfolio.account.equity.toFixed(2) }}
    </p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      portfolio: null
    }
  },
  mounted() {
    this.fetchData();
    setInterval(() => this.fetchData(), 5000);
  },
  methods: {
    async fetchData() {
      try {
        const res = await fetch('http://localhost:8000/api/sync/portfolio');
        this.portfolio = await res.json();
      } catch (err) {
        console.error(err);
      }
    }
  }
}
</script>
```

### Plain JavaScript
```html
<div id="portfolio">
  <p>Balance: <span id="balance">--</span></p>
  <p>Equity: <span id="equity">--</span></p>
  <p>Positions: <span id="positions">--</span></p>
  <p>Profit: <span id="profit">--</span></p>
</div>

<script>
async function updatePortfolio() {
  try {
    const res = await fetch('http://localhost:8000/api/sync/portfolio');
    const data = await res.json();
    
    document.getElementById('balance').textContent = 
      data.account.balance.toFixed(2);
    document.getElementById('equity').textContent = 
      data.account.equity.toFixed(2);
    document.getElementById('positions').textContent = 
      data.summary.open_positions;
    document.getElementById('profit').textContent = 
      data.summary.total_profit.toFixed(2);
  } catch (err) {
    console.error(err);
  }
}

// Update immediately and then every 5 seconds
updatePortfolio();
setInterval(updatePortfolio, 5000);
</script>
```

---

## 🚀 NEXT LEVEL: Independent Running

### Want it to run even when you close VS Code?

**Option 1: Windows Task Scheduler (Easiest)**
1. Press `Win + R`, type `taskschd.msc`
2. Create Basic Task
3. Name: "Turbo Sync"
4. Trigger: At startup
5. Action: Run program → `python.exe`
6. Arguments: `C:\path\to\local_start.py`
7. Click OK

Now it runs automatically when Windows starts!

**Option 2: Windows Service**
```powershell
# PowerShell as Admin
pip install pywin32
python -m pywin32_postinstall -install
New-Service -Name TurboSync -BinaryPathName "python C:\path\to\local_start.py" -DisplayName "Turbo Sync Service"
Start-Service -Name TurboSync
```

**Option 3: Screen or tmux (Linux/Mac)**
```bash
# Keep it running in background
tmux new-session -d -s turbo "python local_start.py"

# View logs
tmux capture-pane -p -t turbo
```

---

## ✅ VERIFICATION CHECKLIST

- [ ] `.env` has `MOCK_MODE=0`
- [ ] MT5 terminal is open on your PC
- [ ] `python local_start.py` shows "✅ Connected"
- [ ] `http://localhost:8000/api/sync/status` shows real balance
- [ ] Frontend is updated to use new endpoints
- [ ] Netlify showing real data (not mock)
- [ ] Updates happen every 5 seconds
- [ ] Can access from another device

---

## 📞 EMERGENCY DEBUG

If something's wrong, run this:

```bash
# Full diagnostic
echo "=== Checking .env ===" && \
grep "MOCK_MODE" .env && \
echo "=== Testing MT5 ===" && \
python -c "import MetaTrader5 as mt5; print('MT5:', 'OK' if mt5.initialize() else 'FAIL')" && \
echo "=== Starting sync ===" && \
python local_start.py
```

---

## 🎊 YOU'RE DONE!

Your system is now live with:
✅ Real MT5 data  
✅ Real-time cloud sync  
✅ Live Netlify updates  
✅ Access from anywhere  
✅ Zero mock data  

**Enjoy your production-grade trading platform!** 🚀

---

**Questions?** See `LOCAL_SETUP_GUIDE.md` for full setup instructions  
**Issues?** Check troubleshooting section above  
**Want more?** Read `SIGNAL_SYSTEM_INTEGRATION.md` for strategy automation
