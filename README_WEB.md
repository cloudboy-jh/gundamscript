# gundam-buyer web app

Minimal Flask app for automated P-Bandai checkout. Terminal-native brutalist design.

## Quick Start (Local)

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run server
python app.py

# Open browser
# http://localhost:5000
```

Your friend visits the URL, enters credentials, hits start.

## Deploy Options

### Option 1: Railway (Easiest)

1. Push to GitHub
2. Go to railway.app
3. "New Project" → "Deploy from GitHub"
4. Select your repo
5. Railway auto-detects Python and deploys

**Important:** Railway needs to run non-headless Playwright, which requires a display server. Add this to your Railway environment:

```
DISPLAY=:99
```

Then update `app.py` line 79 to:
```python
browser = p.chromium.launch(headless=True)  # Change to True for Railway
```

**Better approach for Railway:** Since Railway doesn't support GUI browsers well, consider using Fly.io or a VPS instead.

### Option 2: Fly.io (Recommended)

Create `fly.toml`:
```toml
app = "gundam-buyer"
primary_region = "lax"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "5000"

[[services]]
  http_checks = []
  internal_port = 5000
  processes = ["app"]
  protocol = "tcp"
  script_checks = []

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

Deploy:
```bash
flyctl launch
flyctl deploy
```

### Option 3: Digital Ocean / Linode VPS (Most Reliable)

```bash
# On VPS
sudo apt update
sudo apt install python3-pip xvfb

# Clone your repo
git clone <your-repo>
cd gundam-buyer

# Install deps
pip3 install -r requirements.txt
playwright install chromium
playwright install-deps

# Run with virtual display (for headless GUI)
xvfb-run python3 app.py
```

Keep it running with systemd:

Create `/etc/systemd/system/gundam-buyer.service`:
```ini
[Unit]
Description=Gundam Buyer
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/your-user/gundam-buyer
Environment="DISPLAY=:99"
ExecStart=/usr/bin/xvfb-run python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable gundam-buyer
sudo systemctl start gundam-buyer
```

### Option 4: Run on Your Machine, Expose with ngrok

Super simple for one-time use:

```bash
# Terminal 1: Run the app
python app.py

# Terminal 2: Expose it
ngrok http 5000
```

Send your friend the ngrok URL. Done.

## Architecture

```
User Browser
    ↓
Flask Server (app.py)
    ↓
Playwright (launches Chrome)
    ↓
P-Bandai.com
```

- Server-Sent Events (SSE) for real-time logs
- Browser runs on server, not client
- User just sees the web interface
- Browser window opens on server for manual checkout completion

## Security Notes

⚠️ **This is for personal use only:**
- Credentials sent over HTTP if not using HTTPS
- No authentication on the web interface
- Anyone with the URL can use it
- Consider adding basic auth if deploying publicly

Add basic auth:
```python
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash

auth = HTTPBasicAuth()

users = {
    "your-friend": "some-password-hash"
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

# Then add @auth.login_required to routes
```

## Troubleshooting

### "Browser won't launch"
- Make sure `playwright install chromium` ran
- On Linux: `playwright install-deps`
- Check you have display server (xvfb on headless servers)

### "Can't see browser window"
- Browser runs on the server, not client
- If deploying remote, you won't see the window
- User needs to complete checkout manually on the server

### "Port 5000 already in use"
Change the port in `app.py`:
```python
app.run(host='0.0.0.0', port=8080)
```

## Design

Uses jack-tech-brutalist design system:
- JetBrains Mono monospace font
- Terminal-native dark theme
- Sharp corners, no bullshit
- Information-dense
- Fast interactions

## License

Do whatever. P-Bandai might not like automated purchases though.
