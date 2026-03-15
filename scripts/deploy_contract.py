"""
deploy_contract.py

Compiles and deploys EvidenceRegistry.sol to a local Ganache devnet and writes the
deployed contract address into config.json.

Security note:
- The deployer private key is taken from the ETH_PRIVATE_KEY environment variable.
- Do not hardcode private keys in the repo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from solcx import compile_standard, install_solc
from web3 import Web3
from eth_account import Account


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PROJECT_ROOT / "contracts" / "EvidenceRegistry.sol"


@dataclass
class Config:
    rpc_url: str
    chain_id: int
    solidity_version: str
    contract_name: str
    contract_address: str
    paths: Dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> Tuple[Config, Path]:
    cfg_path = PROJECT_ROOT / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError("config.json not found. Copy config.example.json to config.json and edit as needed.")
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return Config(
        rpc_url=data["rpc_url"],
        chain_id=int(data["chain_id"]),
        solidity_version=data.get("solidity_version", "0.8.20"),
        contract_name=data.get("contract_name", "EvidenceRegistry"),
        contract_address=data.get("contract_address", ""),
        paths=data["paths"],
    ), cfg_path


def append_log(logs_dir: Path, filename: str, test_id: str, message: str) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / filename
    line = f"{utc_now_iso()}\t{test_id}\t{message}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def compile_contract(solidity_version: str) -> Tuple[Dict[str, Any], str]:
    install_solc(solidity_version)

    source = CONTRACT_PATH.read_text(encoding="utf-8")
    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {CONTRACT_PATH.name: {"content": source}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode"]
                    }
                }
            },
        },
        solc_version=solidity_version,
    )

    return compiled, CONTRACT_PATH.name


def get_abi_and_bytecode(compiled: Dict[str, Any], source_name: str, contract_name: str) -> Tuple[Any, str]:
    contracts = compiled["contracts"][source_name]
    if contract_name not in contracts:
        raise KeyError(f"Contract '{contract_name}' not found in compilation output. Found: {list(contracts.keys())}")
    abi = contracts[contract_name]["abi"]
    bytecode = contracts[contract_name]["evm"]["bytecode"]["object"]
    if not bytecode:
        raise ValueError("Empty bytecode; compilation failed.")
    return abi, bytecode


def deploy(w3: Web3, chain_id: int, abi: Any, bytecode: str, deployer_privkey: str) -> str:
    acct = Account.from_key(deployer_privkey)
    nonce = w3.eth.get_transaction_count(acct.address)

    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = contract.constructor().build_transaction(
        {
            "from": acct.address,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": 2_000_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError(f"Deployment failed. tx={tx_hash.hex()}")
    return receipt.contractAddress


def main() -> None:
    test_id = os.environ.get("TEST_ID", "DEPLOY-RUN")
    cfg, cfg_path = load_config()

    logs_dir = PROJECT_ROOT / cfg.paths["logs_dir"]
    append_log(logs_dir, "encryption_anchor.log", test_id, "START deploy_contract")

    priv = os.environ.get("ETH_PRIVATE_KEY")
    if not priv:
        raise EnvironmentError("ETH_PRIVATE_KEY is not set. Export a Ganache private key to this environment variable.")

    w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {cfg.rpc_url}. Is Ganache running?")

    compiled, source_name = compile_contract(cfg.solidity_version)
    abi, bytecode = get_abi_and_bytecode(compiled, source_name, cfg.contract_name)
    contract_address = deploy(w3, cfg.chain_id, abi, bytecode, priv)

    # Write address into config.json
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    raw["contract_address"] = contract_address
    cfg_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    append_log(logs_dir, "encryption_anchor.log", test_id, f"DEPLOYED contract_address={contract_address}")
    append_log(logs_dir, "encryption_anchor.log", test_id, "END deploy_contract OK")
    print(f"[OK] Deployed {cfg.contract_name} at: {contract_address}")
    print(f"[OK] Updated config.json contract_address.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Best-effort logging
        try:
            cfg, _ = load_config()
            logs_dir = PROJECT_ROOT / cfg.paths["logs_dir"]
            append_log(logs_dir, "encryption_anchor.log", os.environ.get("TEST_ID", "DEPLOY-RUN"), f"END deploy_contract ERROR={e}")
        except Exception:
            pass
        raise
