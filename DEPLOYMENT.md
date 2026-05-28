# TURBO EXECUTIONS - Deployment Guide

## Problem Solved
✅ **Authentication** now works with split deployment (frontend on Netlify, backend on Render)
✅ **CORS** enabled for cross-origin requests
✅ **API configuration** automatically detects local vs production backends

## Deployment Architecture

```
┌─────────────────────────┐         ┌──────────────────────────┐
│  Netlify (Frontend)     │         │  Render.com (Backend)    │
│  turbo-executions       │  HTTP   │  turbo-executions-api    │
│  .netlify.app           │◄───────►│  .onrender.com           │
│  (Static HTML/JS)       │         │  (FastAPI Python)        │
└─────────────────────────┘         └──────────────────────────┘
```

## Setup Instructions

### 1. Deploy Backend to Render.com

#### Step 1a: Push to GitHub
```bash
git add .
git commit -m "Fix authentication: add CORS support and API configuration"
git push origin main
```

#### Step 1b: Deploy on Render
1. Go to [render.com](https://render.com)
2. Sign up / Log in
3. Click **"New +"** → **"Web Service"**
4. Connect your GitHub repository
5. Choose branch: `main`
6. Name: `turbo-executions-api`
7. Environment: Select **Python**
8. Build Command: (leave default - Render reads `render.yaml`)
9. Start Command: (leave default - Render reads `render.yaml`)
10. Click **"Advanced"** and add Environment Variables:
    - `ACCESS_CODE` = `TURBO-EXECUTIONS`
    - `MOCK_MODE` = `1`
    - `MT5_LOGIN` = (your MT5 login if available)
    - `MT5_PASSWORD` = (your MT5 password if available)
    - `MT5_SERVER` = (your MT5 server if available)

11. Click **"Deploy"** and wait (2-3 minutes)
12. Note your backend URL: `https://turbo-executions-api.onrender.com`

### 2. Update Frontend with Backend URL

After your Render backend is deployed, update the frontend configuration:

Edit `app/web/static/index.html` line 310 and replace:
```javascript
// Before:
const backendUrl = localStorage.getItem('API_BASE_URL');
if (backendUrl) return backendUrl;

// After - add this:
// Production backend URL
return 'https://turbo-executions-api.onrender.com';
```

Or use environment variable:
```bash
# Set this in your browser console once to persist:
localStorage.setItem('API_BASE_URL', 'https://turbo-executions-api.onrender.com');
```

### 3. Deploy Frontend to Netlify

1. Go to [netlify.com](https://netlify.com)
2. Sign up / Log in
3. Click **"Add new site"** → **"Import an existing project"**
4. Choose GitHub and select your repository
5. Build command: (leave empty)
6. Publish directory: `app/web/static`
7. Click **"Deploy"**
8. Note your frontend URL: `https://turbo-executions.netlify.app`

### 4. Test Authentication

1. Go to your Netlify frontend URL
2. Enter access code: `TURBO-EXECUTIONS`
3. Click "UNLOCK"
4. ✅ Should see "Login successful" and dashboard loads

## Local Development

### Run Locally (Backend)
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ACCESS_CODE=TURBO-EXECUTIONS
export MOCK_MODE=1
export PORT=8000

# Run backend
uvicorn app.api.server:app --reload
```

### Access Dashboard
- Frontend: http://localhost:3000 (if you have a dev server)
- Or directly: http://localhost:8000 (serves static HTML)
- Access code: `TURBO-EXECUTIONS`

## Environment Variables

### Backend (Render or local)
| Variable | Example | Required |
|----------|---------|----------|
| `ACCESS_CODE` | `TURBO-EXECUTIONS` | ✅ Yes |
| `MOCK_MODE` | `1` | No (default: 0) |
| `MT5_LOGIN` | `405773` | If using real MT5 |
| `MT5_PASSWORD` | `password` | If using real MT5 |
| `MT5_SERVER` | `EquityEdge-Trade` | If using real MT5 |
| `MT5_PATH` | `/path/to/terminal64.exe` | If using real MT5 |

### Frontend (Netlify)
No specific environment variables needed. Backend URL is detected automatically:
- **Local**: `http://localhost:8000`
- **Production**: Set via `localStorage.setItem('API_BASE_URL', '...')`

## Troubleshooting

### "Login failed" Error
1. Check that `ACCESS_CODE` is set correctly on Render dashboard
2. Verify backend is deployed and running (check Render logs)
3. Open browser console (F12) and check Network tab for error details
4. Try the "USE DEMO (NO AUTH)" button to test connectivity

### Backend takes time to respond
- Render's free tier spins down after 15 minutes of inactivity
- First request will be slow (cold start)
- Premium tier recommended for production

### CORS errors
- Already configured in FastAPI backend
- If still issues, check browser console for specific error

### WebSocket Connection Issues
- Ensure Render backend URL is correct
- Check Network tab in browser dev tools
- Verify `wss://` protocol is being used for HTTPS frontend

## File Changes Summary

1. **`netlify.toml`** - Simplified for static frontend only
2. **`app/api/server.py`** - Added CORS middleware
3. **`app/web/static/index.html`** - Added API configuration and routing
4. **`render.yaml`** - New file for Render deployment
5. **`api-config.js`** - Reference configuration (optional)

## Next Steps

1. ✅ Deploy backend to Render (5 mins)
2. ✅ Update frontend API URL
3. ✅ Deploy frontend to Netlify (2 mins)
4. ✅ Test login with `TURBO-EXECUTIONS`
5. Customize `ACCESS_CODE` as needed

## Support

For issues:
- Check Render logs: Your Render dashboard → Select web service → Logs
- Check browser console: F12 → Console tab
- Check Network tab: F12 → Network tab → Look for failed requests
