#!/usr/bin/env python3
"""
InstaGrowth Pro - Local Server with SearchApi Instagram Profile Integration
Enforces Domain-Level & Same-Origin security.
External scrapers, third-party sites, or unauthorized servers receive 401 Unauthorized.
"""

import os
import sys
import json
import time
import mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote_plus, unquote
import urllib.request
import urllib.error

# Directory configuration
BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "instagrowth_pro_live_profile_counter_success_flow.html"
ENV_FILE = BASE_DIR / ".env"

# Load environment variables from .env
def load_env(env_path):
    if not env_path.is_file():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v

load_env(ENV_FILE)

API_KEY = os.environ.get("SEARCHAPI_API_KEY", "")
PORT = int(os.environ.get("PORT", "5000"))
HOST = os.environ.get("HOST", "0.0.0.0")

# In-memory cache for profiles (TTL = 15 minutes)
PROFILE_CACHE = {}
CACHE_TTL = 900  # 15 minutes


class RequestHandler(BaseHTTPRequestHandler):
    def send_cors_headers(self, origin=None):
        req_origin = origin or self.headers.get("Origin") or f"http://{self.headers.get('Host', 'localhost')}"
        self.send_header("Access-Control-Allow-Origin", req_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")
        self.send_header("Vary", "Origin, Referer")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only=False):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API: SearchApi Instagram Profile Fetch (Domain-Protected)
        if path == "/api/profile":
            self.handle_profile_api(query, head_only=head_only)
            return

        # API: Avatar Image Proxy
        if path == "/api/avatar-proxy":
            self.handle_avatar_proxy(query, head_only=head_only)
            return

        # Serve Main HTML
        if path in ("/", "/index.html", "/instagrowth_pro_live_profile_counter_success_flow.html"):
            self.serve_file(HTML_FILE, "text/html; charset=utf-8", head_only=head_only)
            return

        # Serve static assets (e.g. /logo/screen.png)
        relative_path = path.lstrip("/")
        safe_file = (BASE_DIR / relative_path).resolve()

        if str(safe_file).startswith(str(BASE_DIR)) and safe_file.is_file():
            mime_type, _ = mimetypes.guess_type(str(safe_file))
            if not mime_type:
                mime_type = "application/octet-stream"
            self.serve_file(safe_file, mime_type, head_only=head_only)
            return

        # 404 Fallback
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        if not head_only:
            self.wfile.write(b"404 Not Found")

    def serve_file(self, file_path, content_type, head_only=False):
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_cors_headers()
            self.end_headers()
            if not head_only:
                self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            if not head_only:
                self.wfile.write(f"Error reading file: {e}".encode("utf-8"))

    def is_authorized_origin(self):
        """
        Enforce Domain-Level Blocking:
        Only allow requests originating from our own website/host.
        """
        host_header = (self.headers.get("Host") or "").split(":")[0].lower()
        origin = self.headers.get("Origin")
        referer = self.headers.get("Referer")
        sec_fetch_site = self.headers.get("Sec-Fetch-Site")
        client_signature = self.headers.get("X-Requested-With")

        # 1. Block cross-site browser fetches
        if sec_fetch_site and sec_fetch_site == "cross-site":
            return False, "Cross-site request blocked"

        # 2. Check internal client signature
        if client_signature != "InstaGrowthApp":
            return False, "Missing authorized client signature"

        def matches_domain(hostname):
            if not hostname:
                return False
            h = hostname.lower()
            return h in (host_header, "localhost", "127.0.0.1") or h.endswith(".pages.dev")

        # 3. Check Origin header
        if origin:
            try:
                origin_host = urlparse(origin).hostname
                if not matches_domain(origin_host):
                    return False, f"Origin {origin_host} not permitted"
            except Exception:
                return False, "Malformed Origin"

        # 4. Check Referer header
        if referer:
            try:
                referer_host = urlparse(referer).hostname
                if not matches_domain(referer_host):
                    return False, f"Referer {referer_host} not permitted"
            except Exception:
                return False, "Malformed Referer"

        # 5. Direct requests without Origin or Referer (raw curl / unauthorized bot)
        if not origin and not referer:
            return False, "Direct external API access prohibited"

        return True, "Authorized"

    def handle_profile_api(self, query, head_only=False):
        # Security validation: Domain-level blocking
        authorized, reason = self.is_authorized_origin()
        if not authorized:
            self.send_json({
                "status": "error",
                "code": 401,
                "message": "Unauthorized: Access restricted to authorized website origin only",
                "detail": reason
            }, 401, head_only=head_only)
            return

        username = query.get("username", [""])[0].strip()
        if not username:
            self.send_json({"status": "error", "message": "Username is required"}, 400, head_only=head_only)
            return

        # Clean username (strip @ or whitespace)
        clean_user = username.lstrip("@").strip()
        if not clean_user:
            self.send_json({"status": "error", "message": "Invalid username"}, 400, head_only=head_only)
            return

        # Check Cache
        cache_key = clean_user.lower()
        now = time.time()
        if cache_key in PROFILE_CACHE:
            cached_time, cached_data = PROFILE_CACHE[cache_key]
            if now - cached_time < CACHE_TTL:
                self.send_json({"status": "success", "cached": True, "profile": cached_data}, head_only=head_only)
                return

        # Check API Key
        current_api_key = os.environ.get("SEARCHAPI_API_KEY", API_KEY)
        if not current_api_key:
            self.send_json({"status": "error", "message": "SearchApi API key not found in .env"}, 500, head_only=head_only)
            return

        # Fetch from SearchApi
        api_url = f"https://www.searchapi.io/api/v1/search?engine=instagram_profile&username={quote_plus(clean_user)}&api_key={quote_plus(current_api_key)}"
        
        try:
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "InstaGrowthPro/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as res:
                response_bytes = res.read()
                data = json.loads(response_bytes.decode("utf-8"))

            profile = data.get("profile")
            if not profile:
                err_msg = data.get("error") or "Profile not found or private"
                self.send_json({"status": "error", "message": err_msg}, 404, head_only=head_only)
                return

            # Format normalized response
            extracted = {
                "username": profile.get("username", clean_user),
                "name": profile.get("name") or clean_user,
                "bio": profile.get("bio", ""),
                "avatar": profile.get("avatar", ""),
                "is_verified": bool(profile.get("is_verified", False)),
                "posts": int(profile.get("posts", 0)),
                "followers": int(profile.get("followers", 0)),
                "following": int(profile.get("following", 0)),
                "external_link": profile.get("external_link", "")
            }

            # Cache the result
            PROFILE_CACHE[cache_key] = (now, extracted)

            self.send_json({"status": "success", "cached": False, "profile": extracted}, head_only=head_only)

        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                msg = err_body.get("error") or str(e)
            except Exception:
                msg = f"HTTP Error {e.code}: {e.reason}"
            self.send_json({"status": "error", "message": msg}, e.code, head_only=head_only)
        except Exception as e:
            self.send_json({"status": "error", "message": f"Server error: {str(e)}"}, 500, head_only=head_only)

    def handle_avatar_proxy(self, query, head_only=False):
        img_url = query.get("url", [""])[0]
        if not img_url:
            self.send_response(400)
            self.end_headers()
            return

        try:
            req = urllib.request.Request(
                img_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.instagram.com/"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                img_bytes = res.read()
                content_type = res.headers.get("Content-Type", "image/jpeg")
                
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(img_bytes)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_cors_headers()
                self.end_headers()
                if not head_only:
                    self.wfile.write(img_bytes)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            if not head_only:
                self.wfile.write(f"Image fetch failed: {e}".encode("utf-8"))

    def send_json(self, payload, code=200, head_only=False):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def run():
    server = HTTPServer((HOST, PORT), RequestHandler)
    print(f"==================================================")
    print(f"InstaGrowth Pro Server running at:")
    print(f"  Local:   http://localhost:{PORT}")
    print(f"  Network: http://{HOST}:{PORT}")
    print(f"  Security: Strict Domain-Level & Origin Protection Active")
    print(f"==================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()

if __name__ == "__main__":
    run()
