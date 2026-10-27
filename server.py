#!/usr/bin/env python3
"""
Zien Crypto Terminal Top-Level Launcher
Pure Python 3.12+ Standard Library Backend.
"""
import argparse
import sys
from pathlib import Path

# Add project root and cryptoscope package to sys.path
root_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(root_dir / "cryptoscope"))
sys.path.insert(0, str(root_dir))

from cryptoscope.server import run_server

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Zien Crypto Quantitative Terminal Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8900, help="Port (default: 8900)")
    args = parser.parse_args()

    run_server(args.host, args.port)
