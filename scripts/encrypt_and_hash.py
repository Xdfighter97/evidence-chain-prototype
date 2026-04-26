"""
encrypt_and_hash.py

Reads hashes_export.json, encrypts each evidence file using ChaCha20-Poly1305,
computes SHA-256 of ciphertext, writes encrypted artifacts and per-item meta.json,
and optionally anchors ciphertext hashes on-chain via EvidenceRegistry.

Forensic/security design notes:
- Encryption key is provided via env var EVIDENCE_KEY_B64 (base64 of 32 bytes).
- A fresh 12-byte nonce is generated per file (ChaCha20-Poly1305).
- Meta includes original hash (from acquisition), ciphertext hash, nonce, algorithms, and timestamps.
- Logs are append-only and timestamped; include TEST_ID for correlation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from eth_account import Account
from solcx import compile_standard, install_solc
from web3 import Web3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SOURCE_PATH = PROJECT_ROOT / "contracts" / "EvidenceRegistry.sol"


@dataclass
class PathsConfig:
    evidence_root: Path
    hashes_export_json: Path
    encrypted_root: Path
    metadata_root: Path
    logs_dir: Path


@dataclass
class AppConfig:
    rpc_url: str
    chain_id: int
    solidity_version: str
    contract_name: str
    contract_address: str
    default_metadata_prefix: str
    paths: PathsConfig


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_log(log_path: Path, test_id: str, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now_iso()}\t{test_id}\t{message}\n")


def load_config() -> AppConfig:
    cfg_path = PROJECT_ROOT / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError("config.json not found. Copy config.example.json to config.json and edit as needed.")
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))

    p = raw["paths"]
    paths = PathsConfig(
        evidence_root=PROJECT_ROOT / p["evidence_root"],
        hashes_export_json=PROJECT_ROOT / p["hashes_export_json"],
        encrypted_root=PROJECT_ROOT / p["encrypted_root"],
        metadata_root=PROJECT_ROOT / p["metadata_root"],
        logs_dir=PROJECT_ROOT / p["logs_dir"],
    )

    return AppConfig(
        rpc_url=raw["rpc_url"],
        chain_id=int(raw["chain_id"]),
        solidity_version=raw.get("solidity_version", "0.8.20"),
        contract_name=raw.get("contract_name", "EvidenceRegistry"),
        contract_address=raw.get("contract_address", ""),
        default_metadata_prefix=raw.get("default_metadata_prefix", ""),
        paths=paths,
    )


def load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"hashes_export.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_key_from_env() -> bytes:
    b64 = os.environ.get("EVIDENCE_KEY_B64")
    if not b64:
        raise EnvironmentError("EVIDENCE_KEY_B64 is not set (base64 of 32 random bytes).")
    key = base64.b64decode(b64)
    if len(key) != 32:
        raise ValueError(f"EVIDENCE_KEY_B64 decoded length is {len(key)} bytes; expected 32.")
    return key


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def compile_contract_abi(solidity_version: str, contract_name: str) -> Any:
    install_solc(solidity_version)
    source = CONTRACT_SOURCE_PATH.read_text(encoding="utf-8")
    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {CONTRACT_SOURCE_PATH.name: {"content": source}},
            "settings": {"outputSelection": {"*": {"*": ["abi"]}}},
        },
        solc_version=solidity_version,
    )
    return compiled["contracts"][CONTRACT_SOURCE_PATH.name][contract_name]["abi"]


def get_registry(w3: Web3, cfg: AppConfig) -> Any:
    if not cfg.contract_address:
        raise ValueError("config.json contract_address is empty. Deploy the contract first.")
    abi = compile_contract_abi(cfg.solidity_version, cfg.contract_name)
    return w3.eth.contract(address=Web3.to_checksum_address(cfg.contract_address), abi=abi)


def anchor_hash(
    w3: Web3,
    cfg: AppConfig,
    ciphertext_hash_bytes32: bytes,
    metadata_string: str,
    privkey: str,
) -> str:
    registry = get_registry(w3, cfg)
    acct = Account.from_key(privkey)

    nonce = w3.eth.get_transaction_count(acct.address)
    tx = registry.functions.registerEvidence(ciphertext_hash_bytes32, metadata_string).build_transaction(
        {
            "from": acct.address,
            "nonce": nonce,
            "chainId": cfg.chain_id,
            "gas": 250_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError(f"registerEvidence failed. tx={tx_hash.hex()}")
    return tx_hash.hex()


def build_metadata_string(cfg: AppConfig, item: Dict[str, Any]) -> str:
    # Keep it short: contract stores a string, but you should treat it like a small pointer.
    # You can replace this later with a structured CID/pointer scheme.
    prefix = cfg.default_metadata_prefix.strip()
    rel = item["relative_path"]
    if prefix:
        return f"{prefix};PATH={rel}"
    return f"PATH={rel}"


def encrypt_one(
    key: bytes,
    evidence_path: Path,
    encrypted_path: Path,
    aad: bytes,
) -> Tuple[bytes, bytes]:
    """
    Encrypts file bytes -> ciphertext using ChaCha20-Poly1305.
    Returns (nonce, ciphertext).
    """
    plaintext = evidence_path.read_bytes()
    nonce = os.urandom(12)  # ChaCha20-Poly1305 uses 12-byte nonce
    aead = ChaCha20Poly1305(key)
    ciphertext = aead.encrypt(nonce, plaintext, aad)
    ensure_parent(encrypted_path)
    encrypted_path.write_bytes(ciphertext)
    return nonce, ciphertext


def main() -> None:
    test_id = os.environ.get("TEST_ID", "ENC-RUN")
    cfg = load_config()
    log_path = cfg.paths.logs_dir / "encryption_anchor.log"
    append_log(log_path, test_id, "START encrypt_and_hash")

    key = get_key_from_env()

    manifest = load_manifest(cfg.paths.hashes_export_json)
    items: List[Dict[str, Any]] = manifest.get("items", [])
    if not items:
        raise ValueError("Manifest contains no items.")

    do_anchor = os.environ.get("ANCHOR_ONCHAIN", "0") == "1"
    privkey = os.environ.get("ETH_PRIVATE_KEY", "")
    w3: Optional[Web3] = None
    if do_anchor:
        if not privkey:
            raise EnvironmentError("ANCHOR_ONCHAIN=1 but ETH_PRIVATE_KEY is not set.")
        w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
        if not w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {cfg.rpc_url}. Is Ganache running?")
        append_log(log_path, test_id, f"ANCHOR enabled contract_address={cfg.contract_address}")

    processed = 0

    for item in items:
        rel = item["relative_path"]
        evidence_path = cfg.paths.evidence_root / rel
        if not evidence_path.exists():
            append_log(log_path, test_id, f"SKIP missing evidence file rel={rel}")
            continue

        # Optional AAD binds manifest context into the encryption authentication tag.
        # In a real system you might use case id + examiner id + relative path + original hash.
        aad_str = f"examiner={manifest.get('examiner_id','')};machine={manifest.get('machine_name','')};rel={rel};origsha256={item['sha256_hex']}"
        aad = aad_str.encode("utf-8")

        encrypted_path = cfg.paths.encrypted_root / (rel + ".enc")
        meta_path = cfg.paths.metadata_root / (rel + ".meta.json")

        nonce, ciphertext = encrypt_one(key, evidence_path, encrypted_path, aad=aad)

        cipher_sha_hex = sha256_hex(ciphertext)
        cipher_sha_bytes = bytes.fromhex(cipher_sha_hex)  # 32 bytes
        cipher_sha_bytes32 = cipher_sha_bytes  # already 32 bytes

        tx_hash: Optional[str] = None
        if do_anchor and w3 is not None:
            metadata_string = build_metadata_string(cfg, item)
            tx_hash = anchor_hash(w3, cfg, cipher_sha_bytes32, metadata_string, privkey)
            append_log(log_path, test_id, f"ANCHORED rel={rel} tx={tx_hash} hash={cipher_sha_hex}")

        meta: Dict[str, Any] = {
            "schema_version": "1.0",
            "generated_utc": utc_now_iso(),
            "relative_path": rel,
            "evidence_plaintext": {
                "sha256_hex": item["sha256_hex"],
                "size_bytes": item["size_bytes"],
                "last_write_utc": item["last_write_utc"],
            },
            "encryption": {
                "algorithm": "ChaCha20-Poly1305",
                "key_source": "env:EVIDENCE_KEY_B64",
                "nonce_b64": base64.b64encode(nonce).decode("ascii"),
                "aad_utf8": aad_str,
            },
            "ciphertext": {
                "file_name": encrypted_path.name,
                "sha256_hex": cipher_sha_hex,
                "sha256_bytes32": "0x" + cipher_sha_hex,
            },
            "blockchain": {
                "network": "ganache-local",
                "rpc_url": cfg.rpc_url,
                "chain_id": cfg.chain_id,
                "contract_address": cfg.contract_address,
                "tx_hash": tx_hash,
            },
        }

        ensure_parent(meta_path)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        processed += 1
        print(f"[OK] Encrypted: {rel} -> {encrypted_path} ; meta -> {meta_path}")

    append_log(log_path, test_id, f"END encrypt_and_hash OK processed={processed} anchor={do_anchor}")
    print(f"[DONE] processed={processed} anchor={do_anchor}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Best-effort logging
        try:
            cfg = load_config()
            append_log(cfg.paths.logs_dir / "encryption_anchor.log", os.environ.get("TEST_ID", "ENC-RUN"), f"END encrypt_and_hash ERROR={e}")
        except Exception:
            pass
        raise
