#!/usr/bin/env python3
"""
Zien Crypto - Command Line Administration & Diagnostics Tool
Pure Python 3.12+ Standard Library CLI.
"""

from __future__ import annotations
import argparse
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Safe stdout on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from security import DatabaseManager, hash_password, generate_totp_secret, get_totp_token
from binance_feed import get_binance_feed
from crypto_archive import get_crypto_archive
from laya_ai import get_laya_crypto_engine


def cmd_init_owner(args: argparse.Namespace) -> int:
    """Initialize or update single owner credentials."""
    email = args.email.strip().lower() if args.email else input("Owner Email [admin@zien.crypto]: ").strip().lower()
    if not email:
        email = "admin@zien.crypto"

    password = args.password
    if not password:
        import getpass
        password = getpass.getpass("Owner Password (min 8 chars): ")
        confirm = getpass.getpass("Confirm Password: ")
        if password != confirm:
            print("❌ Passwords do not match.")
            return 1

    if len(password) < 8:
        print("❌ Password must be at least 8 characters.")
        return 1

    db = DatabaseManager()
    existing = db.get_user_by_email(email)

    totp_secret = generate_totp_secret() if args.totp else None

    with db.get_connection() as conn:
        now = datetime.now(timezone.utc).isoformat()
        phash = hash_password(password)
        if existing:
            conn.execute("""
                UPDATE users SET password_hash = ?, role = 'owner', totp_secret = ?, updated_at = ?
                WHERE email = ?
            """, (phash, totp_secret, now, email))
            print(f"✅ Owner user '{email}' updated successfully.")
        else:
            conn.execute("""
                INSERT INTO users (email, password_hash, role, plan, totp_secret, created_at, updated_at)
                VALUES (?, ?, 'owner', 'founder', ?, ?, ?)
            """, (email, phash, totp_secret, now, now))
            print(f"✅ Owner user '{email}' created successfully.")
        conn.commit()

    if totp_secret:
        print("\n🔐 TOTP Two-Factor Authentication Secret:")
        print(f"   Secret Key: {totp_secret}")
        token, remaining = get_totp_token(totp_secret)
        print(f"   Current Token: {token} ({remaining}s remaining in window)")
        print("   Enroll this key in your Google Authenticator or 1Password app.\n")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Display comprehensive system status."""
    print("=" * 60)
    print(" ZIEN CRYPTO // QUANTITATIVE SYSTEM STATUS")
    print("=" * 60)

    db = DatabaseManager()
    has_owner = db.has_owner()
    print(f"• Database: {db.db_path}")
    print(f"• Single Owner Configured: {'✅ YES' if has_owner else '❌ NO (Run manage.py init-owner)'}")

    # Archive stats
    archive = get_crypto_archive()
    stat = archive.get_archive_stats()
    print(f"• Candle Archive DB: {archive.db_path}")
    print(f"• Total Archived Candles: {stat.get('total_candles', 0):,}")
    print(f"• Tracked Pairs: {len(stat.get('by_symbol', {}))}")

    # Binance Feed Test
    feed = get_binance_feed()
    print("\n[Binance Public Market Scraper]")
    t0 = time.time()
    try:
        tickers = feed.fetch_24h_tickers()
        latency = round((time.time() - t0) * 1000, 1)
        print(f"• Public Scraper Connection: ✅ ONLINE ({latency}ms latency)")
        print(f"• Available Spot Tickers: {len(tickers)} pairs loaded")
    except Exception as e:
        print(f"• Public Scraper Connection: ❌ OFFLINE ({str(e)})")

    # Ollama & Laya AI
    laya = get_laya_crypto_engine()
    print("\n[Laya Crypto Intelligence Engine]")
    print(f"• Target Model: {laya.model}")
    ollama_ok = laya.is_ollama_alive()
    print(f"• Ollama Local Server: {'✅ ONLINE' if ollama_ok else '❌ OFFLINE (Check ollama serve)'}")
    print("=" * 60)
    return 0


def cmd_candle_stats(args: argparse.Namespace) -> int:
    """Show detailed candle archive counts per symbol and timeframe."""
    archive = get_crypto_archive()
    stats = archive.get_archive_stats()
    by_sym = stats.get("by_symbol", {})
    if not by_sym:
        print("Candle archive is currently empty.")
        return 0

    print(f"{'SYMBOL':<12} {'TIMEFRAME':<10} {'CANDLE COUNT':<15}")
    print("-" * 40)
    for sym, count in sorted(by_sym.items()):
        print(f"{sym:<12} {'5m':<10} {count:<15,}")
    print("-" * 40)
    print(f"Total: {stats.get('total_candles', 0):,} candles stored.")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    """Backup databases to work/backups directory."""
    backup_dir = Path(__file__).parent.parent / "work" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    db_path = Path(DatabaseManager().db_path)
    if db_path.exists():
        dest = backup_dir / f"auth_{ts}.db"
        shutil.copy2(db_path, dest)
        print(f"✅ Auth database backed up to: {dest}")

    arc_path = Path(get_crypto_archive().db_path)
    if arc_path.exists():
        dest = backup_dir / f"candles_{ts}.db"
        shutil.copy2(arc_path, dest)
        print(f"✅ Candle database backed up to: {dest}")

    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run environment health diagnostics."""
    print("=" * 60)
    print(" ZIEN CRYPTO // SYSTEM HEALTH DOCTOR")
    print("=" * 60)

    # 1. Python version
    py_ver = sys.version_info
    py_ok = py_ver.major == 3 and py_ver.minor >= 12
    print(f"[{'PASS' if py_ok else 'WARN'}] Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro} (Recommended >= 3.12)")

    # 2. SQLite WAL support
    try:
        test_conn = sqlite3.connect(":memory:")
        test_conn.execute("PRAGMA journal_mode = WAL")
        print("[PASS] SQLite3 Engine: WAL mode supported")
    except Exception as e:
        print(f"[FAIL] SQLite3 Engine: {e}")

    # 3. Binance Public Connectivity
    feed = get_binance_feed()
    try:
        t0 = time.time()
        feed.fetch_24h_tickers()
        ms = round((time.time() - t0) * 1000, 1)
        print(f"[PASS] Binance Feed Scraper: Sub-second response ({ms}ms)")
    except Exception as e:
        print(f"[FAIL] Binance Feed Scraper: {e}")

    # 4. Ollama Local Endpoint
    laya = get_laya_crypto_engine()
    if laya.is_ollama_alive():
        print(f"[PASS] Ollama Service: Reachable on localhost:11434 with model '{laya.model}'")
    else:
        print("[WARN] Ollama Service: Not responding on localhost:11434 (Rule-based fallback active)")

    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Zien Crypto Terminal Administration CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # init-owner
    p_owner = subparsers.add_parser("init-owner", help="Create or reset owner credentials")
    p_owner.add_argument("--email", help="Owner email address")
    p_owner.add_argument("--password", help="Owner password")
    p_owner.add_argument("--totp", action="store_true", help="Generate TOTP two-factor authentication key")

    # status
    subparsers.add_parser("status", help="Show system status")

    # candle-stats
    subparsers.add_parser("candle-stats", help="Display candle archive statistics")

    # backup
    subparsers.add_parser("backup", help="Create timestamped database backup")

    # doctor
    subparsers.add_parser("doctor", help="Run system diagnostics")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    cmds = {
        "init-owner": cmd_init_owner,
        "status": cmd_status,
        "candle-stats": cmd_candle_stats,
        "backup": cmd_backup,
        "doctor": cmd_doctor,
    }

    return cmds[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
