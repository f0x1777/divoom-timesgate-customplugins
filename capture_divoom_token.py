"""
Mitmproxy addon: captures the Divoom auth token when the iOS app connects.

Usage:
  cd /path/to/divoom-timesgate-aifeats
  .venv/bin/mitmdump -p 8080 -s capture_divoom_token.py

Then on iPhone:
  Settings > Wi-Fi > (your network) > Configure Proxy > Manual
  Server: <your-computer-lan-ip>   Port: 8080
  Navigate to http://mitm.it in Safari and install the CA cert (trust it in Settings)
  Open the Divoom app → it will connect and we'll capture the token here.
"""

import json
import os
import re
from mitmproxy import http

TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".divoom_token")
ENV_FILE   = os.path.join(os.path.dirname(__file__), ".env")

DIVOOM_HOST = "appin.divoom-gz.com"

captured = {}


def _save_token(token: str, user_id: str):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token, "user_id": user_id}, f)

    # Also append / update .env
    env_lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            env_lines = [l for l in f.readlines()
                         if not l.startswith("DIVOOM_TOKEN=") and not l.startswith("DIVOOM_USER_ID=")]
    env_lines.append(f"DIVOOM_TOKEN={token}\n")
    env_lines.append(f"DIVOOM_USER_ID={user_id}\n")
    with open(ENV_FILE, "w") as f:
        f.writelines(env_lines)

    print(f"\n{'='*60}")
    print(f"TOKEN CAPTURED!")
    print(f"  Token   : {token[:20]}...")
    print(f"  UserId  : {user_id}")
    print(f"  Saved to: {TOKEN_FILE} and .env")
    print(f"{'='*60}\n")


class DivoomCapture:
    def response(self, flow: http.HTTPFlow):
        if DIVOOM_HOST not in flow.request.pretty_host:
            return

        # Log all Divoom traffic
        path = flow.request.path
        try:
            req_body = flow.request.get_text()
            resp_body = flow.response.get_text() if flow.response else ""
        except Exception:
            return

        print(f"[divoom] {flow.request.method} {path}")

        # Try to extract token from response
        try:
            data = json.loads(resp_body)
            token = data.get("Token", "")
            user_id = str(data.get("UserId", ""))

            if token and user_id and "captured" not in captured:
                captured["token"] = token
                captured["user_id"] = user_id
                _save_token(token, user_id)
        except Exception:
            pass

        # Also look in request body (in case token is sent as auth)
        try:
            req_data = json.loads(req_body)
            token = req_data.get("Token", "")
            user_id = str(req_data.get("UserId", ""))
            if token and user_id and "captured" not in captured:
                captured["token"] = token
                captured["user_id"] = user_id
                _save_token(token, user_id)
        except Exception:
            pass


addons = [DivoomCapture()]
