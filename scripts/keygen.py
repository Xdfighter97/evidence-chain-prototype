#!/usr/bin/env python3
"""
keygen.py

Secure key generation utility for the Evidence Chain system.
Generates cryptographically secure keys and provides secure storage guidance.

Usage:
    python scripts/keygen.py                  # Generate and display key
    python scripts/keygen.py --save           # Generate and save to .env
    python scripts/keygen.py --verify         # Verify current key is valid
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def generate_key() -> bytes:
    """Generate a cryptographically secure 32-byte key."""
    return os.urandom(32)


def key_to_b64(key: bytes) -> str:
    """Encode key as base64 string."""
    return base64.b64encode(key).decode("ascii")


def b64_to_key(b64: str) -> bytes:
    """Decode base64 string to key bytes."""
    return base64.b64decode(b64)


def validate_key(b64: str) -> tuple[bool, str]:
    """Validate a base64-encoded key."""
    try:
        key = b64_to_key(b64)
        if len(key) != 32:
            return False, f"Key length is {len(key)} bytes, expected 32"
        return True, "Key is valid (32 bytes)"
    except Exception as e:
        return False, f"Invalid base64 encoding: {e}"


def save_to_env(key_b64: str) -> None:
    """Append or update key in .env file."""
    env_path = PROJECT_ROOT / ".env"
    
    lines = []
    key_found = False
    
    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("EVIDENCE_KEY_B64="):
                    lines.append(f"EVIDENCE_KEY_B64={key_b64}\n")
                    key_found = True
                else:
                    lines.append(line)
    
    if not key_found:
        lines.append(f"\nEVIDENCE_KEY_B64={key_b64}\n")
    
    with env_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)
    
    print(f"[OK] Key saved to: {env_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and manage encryption keys for Evidence Chain"
    )
    parser.add_argument(
        "--save", 
        action="store_true",
        help="Save generated key to .env file"
    )
    parser.add_argument(
        "--verify",
        action="store_true", 
        help="Verify the current EVIDENCE_KEY_B64 environment variable"
    )
    args = parser.parse_args()

    if args.verify:
        key_b64 = os.environ.get("EVIDENCE_KEY_B64", "")
        if not key_b64:
            print("[ERROR] EVIDENCE_KEY_B64 is not set")
            sys.exit(1)
        valid, msg = validate_key(key_b64)
        if valid:
            print(f"[OK] {msg}")
        else:
            print(f"[ERROR] {msg}")
            sys.exit(1)
        return

    # Generate new key
    key = generate_key()
    key_b64 = key_to_b64(key)
    
    print("")
    print("═" * 70)
    print(" EVIDENCE CHAIN - ENCRYPTION KEY GENERATED")
    print("═" * 70)
    print("")
    print(f"  Key (base64): {key_b64}")
    print("")
    print("  SECURITY REQUIREMENTS:")
    print("  ─────────────────────────────────────────────────────────────────")
    print("  • Store this key SEPARATELY from evidence files")
    print("  • Use secure key management (HSM, vault, encrypted USB)")
    print("  • Document key custodian in chain-of-custody log")
    print("  • NEVER commit keys to version control")
    print("")
    
    if args.save:
        save_to_env(key_b64)
        print("")
        print("  To use this key in your shell session:")
        print(f'    $env:EVIDENCE_KEY_B64 = "{key_b64}"')
    else:
        print("  To save to .env file, run:")
        print("    python scripts/keygen.py --save")
        print("")
        print("  To set in current shell:")
        print(f'    $env:EVIDENCE_KEY_B64 = "{key_b64}"')
    
    print("")
    print("═" * 70)


if __name__ == "__main__":
    main()
