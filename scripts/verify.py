"""
verify.py

Verifies encrypted artifacts using:
1) Local recomputation of ciphertext SHA-256 (matches meta.json)
2) On-chain record lookup (matches ciphertext SHA-256 stored in EvidenceRegistry)

Outputs OK or TAMPERED per artifact.

Notes:
- Does not require the encryption key (verification is over ciphertext).
- Requires contract to be deployed and accessible if on-chain verification is enabled.
"""

from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from solcx import compile_standard, install_solc
from web3 import Web3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SOURCE_PATH = PROJECT_ROOT / "contracts" / "EvidenceRegistry.sol"


@dataclass
class AppConfig:
    rpc_url: str
    chain_id: int
    solidity_version: str
    contract_name: str
    contract_address: str
    encrypted_root: Path
    metadata_root: Path
    logs_dir: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_log(log_path: Path, test_id: str, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now_iso()}\t{test_id}\t{message}\n")


def load_config() -> AppConfig:
    cfg_path = PROJECT_ROOT / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError("config.json not found.")
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    p = raw["paths"]
    return AppConfig(
        rpc_url=raw["rpc_url"],
        chain_id=int(raw["chain_id"]),
        solidity_version=raw.get("solidity_version", "0.8.20"),
        contract_name=raw.get("contract_name", "EvidenceRegistry"),
        contract_address=raw.get("contract_address", ""),
        encrypted_root=PROJECT_ROOT / p["encrypted_root"],
        metadata_root=PROJECT_ROOT / p["metadata_root"],
        logs_dir=PROJECT_ROOT / p["logs_dir"],
    )


def sha256_file_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
        raise ValueError("contract_address is empty in config.json; deploy first.")
    abi = compile_contract_abi(cfg.solidity_version, cfg.contract_name)
    return w3.eth.contract(address=Web3.to_checksum_address(cfg.contract_address), abi=abi)


def verify_one(meta_path: Path, cfg: AppConfig, w3: Optional[Web3]) -> Tuple[str, str]:
    """
    Returns (status, message) where status is "OK" or "TAMPERED".
    """
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    rel = meta["relative_path"]
    expected_cipher_hex = meta["ciphertext"]["sha256_hex"].lower()
    enc_path = cfg.encrypted_root / (rel + ".enc")
    if not enc_path.exists():
        return "TAMPERED", f"missing ciphertext file: {enc_path}"

    actual_cipher_hex = sha256_file_hex(enc_path).lower()
    if actual_cipher_hex != expected_cipher_hex:
        return "TAMPERED", f"ciphertext hash mismatch meta={expected_cipher_hex} actual={actual_cipher_hex}"

    # On-chain check (optional but recommended)
    if w3 is not None:
        registry = get_registry(w3, cfg)
        evidence_hash_bytes32 = bytes.fromhex(expected_cipher_hex)  # 32 bytes
        exists, ts, blk, md = registry.functions.getEvidence(evidence_hash_bytes32).call()
        if not exists:
            return "TAMPERED", "not found on-chain"
        # If it exists, it is keyed by the hash; match is implicit.

    return "OK", "hash matches (meta + ciphertext" + ("" if w3 is None else " + on-chain") + ")"


def main() -> None:
    test_id = os.environ.get("TEST_ID", "VERIFY-RUN")
    cfg = load_config()
    log_path = cfg.logs_dir / "verify.log"
    append_log(log_path, test_id, "START verify")

    do_chain = os.environ.get("VERIFY_ONCHAIN", "1") == "1"
    w3: Optional[Web3] = None
    if do_chain:
        w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
        if not w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {cfg.rpc_url}. Is Ganache running?")
        append_log(log_path, test_id, f"ONCHAIN verify enabled contract_address={cfg.contract_address}")
    else:
        append_log(log_path, test_id, "ONCHAIN verify disabled")

    meta_files = sorted(cfg.metadata_root.rglob("*.meta.json"))
    if not meta_files:
        raise FileNotFoundError(f"No .meta.json files found under: {cfg.metadata_root}")

    ok = 0
    bad = 0

    for mp in meta_files:
        status, msg = verify_one(mp, cfg, w3)
        rel = json.loads(mp.read_text(encoding="utf-8"))["relative_path"]
        line = f"{status}\t{rel}\t{msg}"
        append_log(log_path, test_id, line)
        print(line)
        if status == "OK":
            ok += 1
        else:
            bad += 1

    append_log(log_path, test_id, f"END verify OK={ok} TAMPERED={bad}")
    print(f"[DONE] OK={ok} TAMPERED={bad}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            cfg = load_config()
            append_log(cfg.logs_dir / "verify.log", os.environ.get("TEST_ID", "VERIFY-RUN"), f"END verify ERROR={e}")
        except Exception:
            pass
        raise
