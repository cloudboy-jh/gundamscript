from flask import Flask, render_template, request, jsonify, Response
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import hmac
import os
import threading
import queue
import time
import uuid
from functools import wraps

app = Flask(__name__)

# Store active sessions
sessions = {}

def require_basic_auth(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        user = os.environ.get("BASIC_AUTH_USER")
        password = os.environ.get("BASIC_AUTH_PASSWORD")
        if not user or not password:
            return handler(*args, **kwargs)

        auth = request.authorization
        if not auth:
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Login Required"'},
            )

        if not hmac.compare_digest(auth.username or "", user) or not hmac.compare_digest(
            auth.password or "", password
        ):
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Login Required"'},
            )

        return handler(*args, **kwargs)

    return wrapper

class BrowserSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.log_queue = queue.Queue()
        self.browser = None
        self.page = None
        self.status = "idle"
        
    def log(self, message, level="info"):
        """Add log message to queue"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put({
            "timestamp": timestamp,
            "message": message,
            "level": level
        })

@app.route('/')
@require_basic_auth
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
@require_basic_auth
def start_purchase():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    product_url = data.get('product_url')
    
    if not email or not password or not product_url:
        return jsonify({"error": "Missing required fields"}), 400
    
    # Create new session
    session_id = str(uuid.uuid4())
    session = BrowserSession(session_id)
    sessions[session_id] = session
    
    # Start purchase in background thread
    thread = threading.Thread(
        target=run_purchase,
        args=(session, email, password, product_url),
        daemon=True
    )
    thread.start()
    
    return jsonify({"session_id": session_id})

@app.route('/logs/<session_id>')
@require_basic_auth
def stream_logs(session_id):
    """Server-sent events endpoint for streaming logs"""
    def generate():
        session = sessions.get(session_id)
        if not session:
            yield f"data: {{'error': 'Session not found'}}\n\n"
            return
            
        while True:
            try:
                log = session.log_queue.get(timeout=30)
                yield f"data: {log}\n\n"
                
                if log.get('message') == 'COMPLETE' or log.get('level') == 'error':
                    break
            except queue.Empty:
                yield f"data: {{'ping': true}}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

def run_purchase(session, email, password, product_url):
    """Execute the purchase automation"""
    try:
        session.log("🚀 Starting browser automation...")
        session.status = "running"
        
        with sync_playwright() as p:
            # Launch browser
            headless = os.environ.get("HEADLESS", "true").lower() in ("1", "true", "yes", "on")
            browser = p.chromium.launch(
                headless=headless,
                slow_mo=100
            )
            
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()
            session.browser = browser
            session.page = page
            
            # Login
            session.log("🔐 Logging in to P-Bandai...")
            page.goto('https://p-bandai.com/us/login', wait_until='networkidle')
            
            page.fill('input[type="email"], input[name="email"]', email)
            time.sleep(0.5)
            page.fill('input[type="password"], input[name="password"]', password)
            time.sleep(0.5)
            
            page.click('button[type="submit"], button:has-text("Sign In"), button:has-text("Log In")')
            
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            
            time.sleep(2)
            
            if 'login' in page.url.lower():
                session.log("❌ Login failed - check credentials", "error")
                browser.close()
                session.status = "error"
                return
            
            session.log("✅ Login successful")
            
            # Navigate to product
            session.log(f"🎯 Going to product page...")
            page.goto(product_url, wait_until='networkidle')
            
            # Wait for Add to Cart
            session.log("⏳ Waiting for 'Add to Cart' button...")
            
            selectors = [
                'button:has-text("Add to Cart")',
                'button:has-text("ADD TO CART")',
                'button[class*="add-to-cart"]',
                '.add-to-cart-button'
            ]
            
            found = False
            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=300000, state='visible')
                    session.log(f"🎉 Found Add to Cart button")
                    page.click(selector)
                    found = True
                    break
                except PlaywrightTimeout:
                    continue
            
            if not found:
                session.log("❌ Product not available or sold out", "error")
                browser.close()
                session.status = "error"
                return
            
            time.sleep(2)
            session.log("🛒 Added to cart")
            
            # Go to cart
            session.log("🛍️ Going to cart...")
            page.goto('https://p-bandai.com/us/cart', wait_until='networkidle')
            time.sleep(1)
            
            # Checkout
            session.log("💳 Starting checkout...")
            checkout_selectors = [
                'button:has-text("Checkout")',
                'button:has-text("CHECKOUT")',
                'a:has-text("Checkout")'
            ]
            
            for selector in checkout_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector)
                        session.log("✅ Checkout started")
                        break
                except:
                    continue
            
            time.sleep(2)
            
            # Success
            session.log("=" * 60)
            session.log("✅ BOT COMPLETE")
            session.log("👉 Complete checkout in the browser window")
            session.log("=" * 60)
            session.log("COMPLETE", "success")
            session.status = "complete"
            
            # Don't close browser - user completes manually
            
    except Exception as e:
        session.log(f"❌ Error: {str(e)}", "error")
        session.status = "error"
        if session.browser:
            session.browser.close()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", "5000"))
    app.run(host='0.0.0.0', port=port, debug=False)
