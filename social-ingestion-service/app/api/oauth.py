"""OAuth flow endpoints — real platform OAuth when keys are configured,
development mock OAuth when keys are absent.

Real flow:
  1. GET /oauth/{platform}/init → returns authorization_url on the real platform
  2. User logs in on twitter.com / facebook.com / etc. and grants access
  3. Platform redirects to frontend /oauth/callback?code=...&state=...
  4. Frontend calls POST /oauth/callback to exchange the code

Dev flow (no API keys):
  1. GET /oauth/{platform}/init → returns URL to our built-in branded page
  2. User enters credentials on our dev page (WITH a warning banner)
  3. Dev page redirects to frontend /oauth/callback with a mock code
  4. Frontend calls POST /oauth/callback to complete
"""
from __future__ import annotations

import base64
import hashlib
import html
import logging
import secrets
import time
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, Settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.integrations.registry import SUPPORTED_PLATFORMS, get_platform_client
from app.models.schemas import ConnectResponse
from app.services.ingestion_service import connect_account

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth"])

_pending_states: Dict[str, dict] = {}


def _generate_pkce() -> tuple:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


PLATFORM_BRANDS: Dict[str, dict] = {
    "twitter": {
        "name": "Twitter (X)",
        "color": "#1DA1F2",
        "bg": "#15202B",
        "text": "#FFFFFF",
        "icon": "𝕏",
        "placeholder_user": "@username",
        "permissions": [
            "Read your tweets and profile information",
            "Access your followers and following lists",
            "Read your likes and bookmarks",
        ],
    },
    "facebook": {
        "name": "Facebook",
        "color": "#1877F2",
        "bg": "#F0F2F5",
        "text": "#1C1E21",
        "icon": "f",
        "placeholder_user": "Email or phone number",
        "permissions": [
            "Read your posts and timeline",
            "Access your friends list",
            "Read your likes and reactions",
        ],
    },
    "instagram": {
        "name": "Instagram",
        "color": "#E1306C",
        "bg": "#FAFAFA",
        "text": "#262626",
        "icon": "Instagram",
        "placeholder_user": "Username or email",
        "permissions": [
            "Read your posts and stories",
            "Access your followers and following",
            "Read your comments and likes",
        ],
    },
    "tiktok": {
        "name": "TikTok",
        "color": "#000000",
        "bg": "#121212",
        "text": "#FFFFFF",
        "icon": "♪",
        "placeholder_user": "@username",
        "permissions": [
            "Read your videos and captions",
            "Access engagement metrics",
            "Read your comments and interactions",
        ],
    },
    "snapchat": {
        "name": "Snapchat",
        "color": "#FFFC00",
        "bg": "#FFFC00",
        "text": "#000000",
        "icon": "👻",
        "placeholder_user": "Username",
        "permissions": [
            "Read your story and spotlight content",
            "Access your friends list",
            "Read your Bitmoji and profile data",
        ],
    },
}


# ─── OAuth Init ─────────────────────────────────────────────────────

@router.get("/oauth/{platform}/init")
async def oauth_init(
    platform: str,
    user: dict = Depends(get_current_user),
):
    """Start the OAuth flow. Returns the URL the frontend should open in a popup."""
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(400, f"Unsupported platform: {platform}")

    settings = get_settings()
    state = secrets.token_urlsafe(32)
    callback_url = settings.oauth_redirect_base_url

    state_data: dict = {
        "user_id": user["user_id"],
        "platform": platform,
        "created_at": time.time(),
        "callback_url": callback_url,
    }

    client = get_platform_client(platform)

    if client.has_oauth_keys():
        code_verifier, code_challenge = _generate_pkce()
        state_data["code_verifier"] = code_verifier
        _pending_states[state] = state_data

        url = client.get_oauth_url(state, callback_url, code_challenge=code_challenge)
        return {
            "authorization_url": url,
            "state": state,
            "mode": "live",
        }

    _pending_states[state] = state_data
    dev_url = (
        f"http://localhost:{settings.port}"
        f"/oauth/dev/{platform}/authorize"
        f"?state={state}&redirect_uri={callback_url}"
    )
    return {
        "authorization_url": dev_url,
        "state": state,
        "mode": "development",
    }


# ─── OAuth Callback (code exchange) ────────────────────────────────

@router.post("/oauth/callback")
async def oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Exchange the authorization code for tokens and connect the account."""
    body = await request.json()
    code: str = body.get("code", "")
    state: str = body.get("state", "")
    platform: str = body.get("platform", "")

    if not code or not state:
        raise HTTPException(400, "Missing code or state")

    pending = _pending_states.pop(state, None)
    if not pending:
        raise HTTPException(400, "Invalid or expired state parameter")

    if time.time() - pending["created_at"] > 600:
        raise HTTPException(400, "Authorization session expired (10 min limit)")

    if platform and platform != pending["platform"]:
        raise HTTPException(400, "Platform mismatch")

    platform = pending["platform"]
    user_id = pending["user_id"]
    callback_url = pending.get("callback_url", "")
    code_verifier = pending.get("code_verifier")

    client = get_platform_client(platform)

    if client.has_oauth_keys():
        try:
            token_data = await client.exchange_code(
                code, callback_url, code_verifier=code_verifier
            )
        except Exception as exc:
            logger.error("Token exchange failed for %s: %s", platform, exc)
            raise HTTPException(502, f"Failed to complete {platform} authorization: {exc}")

        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token")
        platform_username = token_data.get("username", "")
        platform_user_id = token_data.get("user_id", "")
    else:
        parts = code.split(":", 2)
        if len(parts) < 2:
            raise HTTPException(400, "Invalid authorization code")
        platform_username = parts[0]
        access_token = hashlib.sha256(code.encode()).hexdigest()
        refresh_token = None
        platform_user_id = f"{platform[:2]}_{platform_username}"

    account = await connect_account(
        db=db,
        user_id=user_id,
        platform=platform,
        access_token=access_token,
        refresh_token=refresh_token,
        platform_user_id=platform_user_id,
        platform_username=platform_username,
    )

    return ConnectResponse(
        id=account.id,
        platform=account.platform,
        platform_username=account.platform_username,
        status="connected",
        connected_at=account.connected_at.isoformat() if account.connected_at else "",
    )


# ─── Development OAuth Server ──────────────────────────────────────

@router.get("/oauth/dev/{platform}/authorize", response_class=HTMLResponse)
async def dev_oauth_authorize_page(
    platform: str,
    state: str = "",
    redirect_uri: str = "",
):
    """Serve a branded dev login page with a prominent warning banner."""
    if platform not in PLATFORM_BRANDS:
        raise HTTPException(400, f"Unknown platform: {platform}")

    brand = PLATFORM_BRANDS[platform]
    permissions_html = "".join(
        f'<li style="padding:6px 0;border-bottom:1px solid rgba(128,128,128,0.15)">'
        f'<span style="color:green;margin-right:8px">&#10003;</span>{html.escape(p)}</li>'
        for p in brand["permissions"]
    )

    is_dark = brand["bg"] in ("#15202B", "#121212")
    input_bg = "#2F3336" if is_dark else "#FFFFFF"
    input_border = "#3E4042" if is_dark else "#DADCE0"
    input_text = "#FFFFFF" if is_dark else "#1C1E21"
    subtle_text = "#8899A6" if is_dark else "#65676B"
    btn_text = "#FFFFFF" if platform != "snapchat" else "#000000"

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Log in to {html.escape(brand["name"])} — Authorize VersionAI</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background: {brand["bg"]};
    color: {brand["text"]};
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}
  .dev-banner {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: linear-gradient(90deg, #F59E0B, #EF4444);
    color: #FFFFFF;
    text-align: center;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    z-index: 999;
    line-height: 1.4;
  }}
  .dev-banner small {{
    display: block;
    font-weight: 400;
    font-size: 11px;
    opacity: .9;
    margin-top: 2px;
  }}
  .card {{
    background: {"#192734" if is_dark else "#FFFFFF"};
    border-radius: 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,{".3" if is_dark else ".1"});
    padding: 32px;
    width: 100%;
    max-width: 420px;
    margin-top: 40px;
  }}
  .logo {{
    width: 48px; height: 48px;
    border-radius: 12px;
    background: {brand["color"]};
    color: {btn_text};
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; font-weight: bold;
    margin: 0 auto 16px;
  }}
  h1 {{ text-align:center; font-size:20px; margin-bottom:4px; }}
  .subtitle {{ text-align:center; color:{subtle_text}; font-size:13px; margin-bottom:24px; }}
  .perms {{
    background: {"#1E2C3A" if is_dark else "#F8F9FA"};
    border-radius:10px; padding:14px 16px; margin-bottom:20px;
  }}
  .perms h3 {{ font-size:13px; color:{subtle_text}; margin-bottom:8px; }}
  .perms ul {{ list-style:none; font-size:13px; }}
  .field {{ margin-bottom:14px; }}
  .field label {{ display:block; font-size:13px; font-weight:600; margin-bottom:6px; }}
  .field input {{
    width:100%; height:40px; border-radius:8px;
    border: 1px solid {input_border};
    background: {input_bg};
    color: {input_text};
    padding: 0 12px; font-size:14px; outline:none;
  }}
  .field input:focus {{ border-color: {brand["color"]}; box-shadow: 0 0 0 2px {brand["color"]}33; }}
  .btn-authorize {{
    width:100%; height:44px; border:none; border-radius:8px;
    background:{brand["color"]}; color:{btn_text};
    font-size:15px; font-weight:600; cursor:pointer;
    margin-top:8px; transition: opacity .15s;
  }}
  .btn-authorize:hover {{ opacity:.9; }}
  .btn-authorize:disabled {{ opacity:.5; cursor:not-allowed; }}
  .btn-cancel {{
    width:100%; height:40px; border:1px solid {input_border};
    border-radius:8px; background:transparent; color:{brand["text"]};
    font-size:14px; cursor:pointer; margin-top:10px;
  }}
  .error {{ color:#EF4444; font-size:13px; margin-top:8px; display:none; }}
  .footer {{ text-align:center; color:{subtle_text}; font-size:11px; margin-top:16px; }}
  .setup-link {{
    display: block;
    text-align: center;
    margin-top: 16px;
    padding: 12px;
    border-radius: 10px;
    background: {"#1E2C3A" if is_dark else "#FFF7ED"};
    border: 1px solid {"#374151" if is_dark else "#FDBA74"};
    font-size: 12px;
    color: {"#FBBF24" if is_dark else "#92400E"};
    line-height: 1.5;
  }}
  .setup-link a {{ color: {brand["color"]}; text-decoration: underline; }}
</style>
</head>
<body>

<div class="dev-banner">
  &#9888; DEVELOPMENT MODE — Credentials are NOT verified against {html.escape(brand["name"])}
  <small>To use real {html.escape(brand["name"])} authentication, configure your API keys in the .env file</small>
</div>

<div class="card">
  <div class="logo">{html.escape(brand["icon"])}</div>
  <h1>Log in to {html.escape(brand["name"])}</h1>
  <p class="subtitle">to continue to VersionAI</p>

  <div class="perms">
    <h3>VersionAI is requesting access to:</h3>
    <ul>{permissions_html}</ul>
  </div>

  <form id="authForm" method="POST" action="/oauth/dev/{platform}/submit">
    <input type="hidden" name="state" value="{html.escape(state)}">
    <input type="hidden" name="redirect_uri" value="{html.escape(redirect_uri)}">

    <div class="field">
      <label>{html.escape(brand["placeholder_user"])}</label>
      <input type="text" name="username" id="username"
             placeholder="{html.escape(brand["placeholder_user"])}"
             required autocomplete="username">
    </div>

    <div class="field">
      <label>Password</label>
      <input type="password" name="password" id="password"
             placeholder="Enter your password"
             required autocomplete="current-password">
    </div>

    <p class="error" id="error">Please enter your username and password</p>

    <button type="submit" class="btn-authorize" id="submitBtn">
      Authorize VersionAI
    </button>
    <button type="button" class="btn-cancel" onclick="window.close()">Cancel</button>
  </form>

  <div class="setup-link">
    <strong>Want real authentication?</strong><br>
    Configure your {html.escape(brand["name"])} developer API keys in<br>
    <code>social-ingestion-service/.env</code>
  </div>

  <p class="footer">
    Development mode — In production, users log in directly on {html.escape(brand["name"])}.
  </p>
</div>

<script>
document.getElementById('authForm').addEventListener('submit', function(e) {{
  var u = document.getElementById('username').value.trim();
  var p = document.getElementById('password').value.trim();
  if (!u || !p) {{
    e.preventDefault();
    document.getElementById('error').style.display = 'block';
    return;
  }}
  document.getElementById('submitBtn').disabled = true;
  document.getElementById('submitBtn').textContent = 'Authorizing...';
}});
</script>
</body>
</html>"""
    return HTMLResponse(page_html)


@router.post("/oauth/dev/{platform}/submit")
async def dev_oauth_submit(
    platform: str,
    request: Request,
):
    """Process the dev OAuth form submission and redirect back with a code."""
    form = await request.form()
    username = str(form.get("username", "")).strip().lstrip("@")
    password = str(form.get("password", ""))
    state = str(form.get("state", ""))
    redirect_uri = str(form.get("redirect_uri", ""))

    if not username or not password:
        raise HTTPException(400, "Username and password are required")

    pending = _pending_states.get(state)
    if not pending or pending["platform"] != platform:
        return HTMLResponse(
            "<h2>Session expired.</h2><p>Please close this window and try again.</p>",
            status_code=400,
        )

    code = f"{username}:{secrets.token_urlsafe(32)}"

    separator = "&" if "?" in redirect_uri else "?"
    target = f"{redirect_uri}{separator}code={code}&state={state}&platform={platform}"

    return RedirectResponse(url=target, status_code=302)
