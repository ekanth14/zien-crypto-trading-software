"""
Zien Crypto — Security, Authentication, Single-Owner Administration, and Rate Limiting
Pure Python standard library implementation with zero external dependencies.
"""

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import struct
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB_PATH = os.environ.get(
    "CRYPTO_DB_PATH",
    str(Path(__file__).parent.parent / "work" / "runtime" / "marketscope_crypto.db"),
)

SESSION_LIFETIME_HOURS = 12


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time verification of password against stored hash."""
    try:
        salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Hash a session token with SHA-256."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_totp_secret() -> str:
    """Generate a 32-character base32 secret for TOTP authenticator enrollment."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("utf-8").rstrip("=")


def get_totp_token(secret: str, interval: int = 30) -> Tuple[str, int]:
    """Generate the current 6-digit TOTP token and seconds remaining in period."""
    pad_len = (8 - len(secret) % 8) % 8
    key = base64.b32decode(secret.upper() + "=" * pad_len)
    epoch = int(time.time())
    step = epoch // interval
    msg = struct.pack(">Q", step)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    code = str((struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF) % 1_000_000).zfill(6)
    rem = interval - (epoch % interval)
    return code, rem


def verify_totp(secret: str, token: str, last_step: Optional[int] = None, interval: int = 30) -> Tuple[bool, Optional[int]]:
    """Verify TOTP token within +/- 1 step window, preventing replay attacks."""
    if not token or len(token) != 6 or not token.isdigit():
        return False, None
    pad_len = (8 - len(secret) % 8) % 8
    try:
        key = base64.b32decode(secret.upper() + "=" * pad_len)
    except Exception:
        return False, None
    now_step = int(time.time()) // interval
    for offset in (0, -1, 1):
        step = now_step + offset
        if last_step is not None and step <= last_step:
            continue
        msg = struct.pack(">Q", step)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        o = h[19] & 15
        expected = str((struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF) % 1_000_000).zfill(6)
        if hmac.compare_digest(token, expected):
            return True, step
    return False, None


class DatabaseManager:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    plan TEXT NOT NULL DEFAULT 'member',
                    totp_secret TEXT,
                    totp_last_step INTEGER,
                    disabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    csrf_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    detail TEXT
                )
            """)
            conn.commit()

    def has_owner(self) -> bool:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT 1 FROM users WHERE role = 'owner' AND disabled = 0 LIMIT 1")
            return cur.fetchone() is not None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
            row = cur.fetchone()
            return dict(row) if row else None

    def create_user(self, email: str, password: str, role: str = "member", totp_secret: Optional[str] = None, plan: str = "member") -> int:
        phash = hash_password(password)
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO users (email, password_hash, role, plan, totp_secret, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (email.strip().lower(), phash, role, plan, totp_secret, now, now))
            conn.commit()
            return cur.lastrowid

    def create_authenticated_session(self, user_id: int, mfa_step: Optional[int] = None) -> Optional[Tuple[str, str]]:
        raw_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        thash = hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(hours=SESSION_LIFETIME_HOURS)).isoformat()
        with self.get_connection() as conn:
            if mfa_step is not None:
                conn.execute("UPDATE users SET totp_last_step = ? WHERE id = ?", (mfa_step, user_id))
            conn.execute("""
                INSERT INTO sessions (user_id, token_hash, csrf_token, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, thash, csrf_token, now.isoformat(), expires))
            conn.commit()
        return raw_token, csrf_token

    def validate_session(self, raw_token: str) -> Optional[Dict[str, Any]]:
        if not raw_token:
            return None
        thash = hash_token(raw_token)
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cur = conn.execute("""
                SELECT s.id as session_id, s.csrf_token, u.id as user_id, u.email, u.role, u.plan, u.disabled
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = ? AND s.expires_at > ?
            """, (thash, now))
            row = cur.fetchone()
            if not row or row["disabled"]:
                return None
            return dict(row)

    def revoke_session(self, raw_token: str) -> None:
        thash = hash_token(raw_token)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (thash,))
            conn.commit()


class RateLimiter:
    """Sliding-window in-memory rate limiter per IP address."""
    def __init__(self, limit: int, window_sec: int):
        self.limit = limit
        self.window_sec = window_sec
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_sec
        history = [t for t in self.requests.get(client_ip, []) if t > cutoff]
        if len(history) >= self.limit:
            self.requests[client_ip] = history
            return False
        history.append(now)
        self.requests[client_ip] = history
        return True

    def retry_after(self, client_ip: str) -> int:
        now = time.time()
        cutoff = now - self.window_sec
        history = [t for t in self.requests.get(client_ip, []) if t > cutoff]
        if not history:
            return 1
        return max(1, int(history[0] + self.window_sec - now))
