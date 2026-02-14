"""Authentication system for GeoFix.

Provides:
  - Email/password signup + login
  - JWT cookie sessions
  - Google and GitHub OAuth flows
  - User management (SQLite)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

logger = logging.getLogger("geofix.web.auth")

# ── Configuration ──────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_EXPIRY = 60 * 60 * 24 * 7  # 7 days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")



# ── Database ───────────────────────────────────────────────────

if "FLY_APP_NAME" in os.environ:
    DB_PATH = Path("/data/users.db")
else:
    DB_PATH = Path(__file__).parent.parent.parent / "data" / "users.db"

AUTH_SCHEMA = """\
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    password_hash TEXT DEFAULT '',
    provider    TEXT DEFAULT 'email',
    provider_id TEXT DEFAULT '',
    avatar_url  TEXT DEFAULT '',
    api_key     TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_provider ON users(provider, provider_id);
"""


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(AUTH_SCHEMA)
    return conn


# ── Password Hashing (no bcrypt dependency) ───────────────────

def _hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${key.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, key_hex = stored.split("$")
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


# ── JWT (minimal, no PyJWT dependency) ─────────────────────────

import base64


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _create_jwt(payload: dict) -> str:
    """Create a simple JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload["exp"] = int(time.time()) + JWT_EXPIRY
    payload["iat"] = int(time.time())

    h = _b64url_encode(json.dumps(header).encode())
    p = _b64url_encode(json.dumps(payload).encode())
    sig = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def _verify_jwt(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h, p, s = parts
        expected_sig = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(s)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(p))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ── Router ─────────────────────────────────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupBody(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


def _set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="geofix_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=JWT_EXPIRY,
        path="/",
    )


def _get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("geofix_token")
    if not token:
        return None
    payload = _verify_jwt(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    db = _get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    if not row:
        return None
    return dict(row)


# ── Endpoints ──────────────────────────────────────────────────


@router.post("/signup")
async def signup(body: SignupBody):
    """Register a new user with email and password."""
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Invalid email")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    db = _get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(409, "Email already registered")

    user_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    password_hash = _hash_password(body.password)

    db.execute(
        """INSERT INTO users (id, email, name, password_hash, provider, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'email', ?, ?)""",
        (user_id, email, body.name or email.split("@")[0], password_hash, now, now),
    )
    db.commit()
    db.close()

    token = _create_jwt({"sub": user_id, "email": email})
    response = JSONResponse({"id": user_id, "email": email, "name": body.name or email.split("@")[0]})
    _set_auth_cookie(response, token)
    return response


@router.post("/login")
async def login(body: LoginBody):
    """Login with email and password."""
    email = body.email.strip().lower()
    db = _get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    if not user or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    user_dict = dict(user)
    token = _create_jwt({"sub": user_dict["id"], "email": user_dict["email"]})
    response = JSONResponse({
        "id": user_dict["id"],
        "email": user_dict["email"],
        "name": user_dict["name"],
        "avatar_url": user_dict["avatar_url"],
    })
    _set_auth_cookie(response, token)
    return response


@router.get("/me")
async def get_me(request: Request):
    """Get the current logged-in user."""
    user = _get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "avatar_url": user["avatar_url"],
        "provider": user["provider"],
    }


@router.post("/logout")
async def logout():
    """Clear the auth cookie."""
    response = JSONResponse({"ok": True})
    response.delete_cookie("geofix_token", path="/")
    return response


# ── Google OAuth ───────────────────────────────────────────────


@router.get("/google")
async def google_login():
    """Redirect to Google OAuth consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
    redirect_uri = f"{BASE_URL}/api/auth/google/callback"
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid+email+profile"
        "&access_type=offline"
    )
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str = ""):
    """Handle Google OAuth callback."""
    if not code:
        raise HTTPException(400, "Missing authorization code")

    import httpx

    redirect_uri = f"{BASE_URL}/api/auth/google/callback"

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(400, f"Token exchange failed: {token_resp.text}")
        tokens = token_resp.json()

        # Get user info
        user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={
            "Authorization": f"Bearer {tokens['access_token']}",
        })
        if user_resp.status_code != 200:
            raise HTTPException(400, "Failed to get user info")
        info = user_resp.json()

    email = info.get("email", "")
    name = info.get("name", "")
    avatar = info.get("picture", "")
    provider_id = info.get("id", "")

    user = _upsert_oauth_user(email, name, avatar, "google", provider_id)

    token = _create_jwt({"sub": user["id"], "email": user["email"]})
    response = RedirectResponse("/chat")
    _set_auth_cookie(response, token)
    return response


# ── GitHub OAuth ───────────────────────────────────────────────


@router.get("/github")
async def github_login():
    """Redirect to GitHub OAuth consent screen."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(501, "GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env")
    url = (
        "https://github.com/login/oauth/authorize?"
        f"client_id={GITHUB_CLIENT_ID}"
        "&scope=user:email"
    )
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(code: str = ""):
    """Handle GitHub OAuth callback."""
    if not code:
        raise HTTPException(400, "Missing authorization code")

    import httpx

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post("https://github.com/login/oauth/access_token", data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
        }, headers={"Accept": "application/json"})
        if token_resp.status_code != 200:
            raise HTTPException(400, "Token exchange failed")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(400, "No access token received")

        # Get user info
        user_resp = await client.get("https://api.github.com/user", headers={
            "Authorization": f"Bearer {access_token}",
        })
        info = user_resp.json()

        # Get email (might be private)
        email = info.get("email", "")
        if not email:
            email_resp = await client.get("https://api.github.com/user/emails", headers={
                "Authorization": f"Bearer {access_token}",
            })
            emails = email_resp.json()
            if isinstance(emails, list):
                primary = next((e for e in emails if e.get("primary")), None)
                if primary:
                    email = primary["email"]
                elif emails:
                    email = emails[0]["email"]

    name = info.get("name") or info.get("login", "")
    avatar = info.get("avatar_url", "")
    provider_id = str(info.get("id", ""))

    if not email:
        email = f"{info.get('login', 'user')}@github.local"

    user = _upsert_oauth_user(email, name, avatar, "github", provider_id)

    token = _create_jwt({"sub": user["id"], "email": user["email"]})
    response = RedirectResponse("/chat")
    _set_auth_cookie(response, token)
    return response


# ── Helpers ────────────────────────────────────────────────────


def _upsert_oauth_user(email: str, name: str, avatar: str, provider: str, provider_id: str) -> dict:
    """Create or update a user from OAuth."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    existing = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        user = dict(existing)
        db.execute(
            "UPDATE users SET name = ?, avatar_url = ?, provider = ?, provider_id = ?, updated_at = ? WHERE id = ?",
            (name or user["name"], avatar or user["avatar_url"], provider, provider_id, now, user["id"]),
        )
        db.commit()
        db.close()
        user["name"] = name or user["name"]
        user["avatar_url"] = avatar or user["avatar_url"]
        return user

    user_id = str(uuid.uuid4())[:12]
    db.execute(
        """INSERT INTO users (id, email, name, password_hash, provider, provider_id, avatar_url, created_at, updated_at)
           VALUES (?, ?, ?, '', ?, ?, ?, ?, ?)""",
        (user_id, email, name, provider, provider_id, avatar, now, now),
    )
    db.commit()
    db.close()
    return {"id": user_id, "email": email, "name": name, "avatar_url": avatar}
