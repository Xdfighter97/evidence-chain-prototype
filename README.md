# Evidence Chain Prototype

**Blockchain-backed digital evidence integrity system** for forensic chain-of-custody.

This prototype demonstrates how to:
- Hash evidence files with cryptographic integrity (SHA-256)
- Encrypt evidence using authenticated encryption (ChaCha20-Poly1305)
- Anchor ciphertext hashes on an Ethereum blockchain (Ganache devnet)
- Verify evidence has not been tampered with

---

## Architecture

┌─────────────────────────────────────────────────────────────────────────┐
│                          EVIDENCE CHAIN PIPELINE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   ACQUIRE    │───▶│   ENCRYPT    │───▶│   ANCHOR     │              │
│  │  PowerShell  │    │    Python    │    │  Ethereum    │              │
│  │  SHA-256     │    │ ChaCha20     │    │  Ganache     │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│  hashes_export.json   *.enc files        On-chain record               │
│                       *.meta.json        (immutable)                   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────┐              │
│  │                      VERIFY                          │              │
│  │   Compare: ciphertext hash ←→ meta.json ←→ chain     │              │
│  └──────────────────────────────────────────────────────┘              │
│                              │                                          │
│                              ▼                                          │
│                      OK ✓ or TAMPERED ✗                                │
└─────────────────────────────────────────────────────────────────────────┘

---

## Prerequisites

| Component | Version | Installation |
|-----------|---------|--------------|
| Windows 11 | 25H2 | - |
| PowerShell | 7.x | Microsoft Store |
| Python | 3.11+ | Microsoft Store |
| Node.js | 18+ | https://nodejs.org |
| Ganache | 7.x | `npm install -g ganache` |

---

## Quick Start (Reproducible)

### 1. Clone and Setup

```powershell

git clone https://github.com/Xdfighter97/evidence-chain-prototype.git
cd evidence-chain-prototype

# Create Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
2. Configure Environment

# Copy example configs
Copy-Item config.example.json config.json
Copy-Item .env.example .env

# Generate encryption key (SAVE THIS SECURELY!)
python scripts/keygen.py --save
3. Start Ganache

# In a separate terminal - use deterministic mode for reproducibility
npx ganache --deterministic
4. Run Complete Pipeline

# Single command runs everything
.\run_pipeline.ps1 -CaseId "CASE2026-001" -ExaminerId "EXAMINER01"

## Directory Structure

evidence-chain-prototype/
├── config.example.json      # Template configuration (copy to config.json)
├── .env.example             # Template for secrets (copy to .env)
├── requirements.txt         # Python dependencies
│
├── contracts/
│   └── EvidenceRegistry.sol # Solidity smart contract
│
├── scripts/
│   ├── run_pipeline.ps1     # One-command full pipeline
│   ├── reset.ps1            # Clean outputs for fresh run
│   ├── keygen.py            # Key generation utility
│   ├── deploy_contract.py   # Deploy smart contract
│   ├── ForensicHashPipeline.ps1  # Evidence acquisition
│   ├── encrypt_and_hash.py  # Encryption + anchoring
│   └── verify.py            # Integrity verification
│
├── evidence/                # Source evidence files
│   ├── doc1.txt
│   ├── doc2.txt
│   ├── notes.log
│   └── images/
│       └── blob.bin
│
├── out/                     # Generated outputs (gitignored)
│   ├── exports/             # Hash manifests
│   ├── encrypted/           # Encrypted files (*.enc)
│   └── metadata/            # Per-file metadata (*.meta.json)
│
└── logs/                    # Append-only audit logs (gitignored)

# Step-by-Step Manual Workflow

If you prefer running each step individually:

Step 1: Deploy Smart Contract

$env:ETH_PRIVATE_KEY = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
python scripts/deploy_contract.py
Step 2: Acquire Evidence Hashes

$env:TEST_ID = "CASE001-RUN001"
pwsh -File scripts/ForensicHashPipeline.ps1 `
  -EvidenceRoot .\evidence `
  -ExaminerId "EXAMINER01" `
  -OutputJson .\out\exports\hashes_export.json `
  -TestId $env:TEST_ID
Step 3: Encrypt and Anchor

# Set encryption key
$env:EVIDENCE_KEY_B64 = "<your-key-from-keygen>"

# Optional: anchor on-chain
$env:ANCHOR_ONCHAIN = "1"
$env:ETH_PRIVATE_KEY = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"

python scripts/encrypt_and_hash.py
Step 4: Verify Integrity

$env:VERIFY_ONCHAIN = "1"  # or "0" for local-only
python scripts/verify.py

# Output Files

hashes_export.json

{
  "schema_version": "1.0",
  "generated_utc": "2026-02-03T18:14:51Z",
  "examiner_id": "EXAMINER01",
  "items": [
    {
      "relative_path": "doc1.txt",
      "size_bytes": 18,
      "sha256_hex": "36e22260a565..."
    }
  ]
}
*.meta.json

{
  "schema_version": "1.0",
  "relative_path": "doc1.txt",
  "evidence_plaintext": {
    "sha256_hex": "36e22260a565...",
    "size_bytes": 18
  },
  "encryption": {
    "algorithm": "ChaCha20-Poly1305",
    "nonce_b64": "dGVzdG5vbmNl..."
  },
  "ciphertext": {
    "sha256_hex": "abc123...",
    "sha256_bytes32": "0xabc123..."
  },
  "blockchain": {
    "contract_address": "0xB270...",
    "tx_hash": "0x9f8e..."
  }
}

# Reset for Fresh Run

# Clean all outputs (preserves evidence, scripts, config)
.\reset.ps1

# Keep logs
.\reset.ps1 -KeepLogs

# Security Notes

Requirement	Implementation
Key Storage	Environment variable, never in repo
Key Generation	Cryptographically secure (os.urandom)
Encryption	ChaCha20-Poly1305 with a unique nonce per file
Integrity	SHA-256 of ciphertext anchored on-chain
Audit Trail: Append-only, timestamped logs with test IDs

# Future Extensions

Hyperledger Fabric
Replace Ganache with Fabric for permissioned enterprise deployment:
Use Fabric SDK for Python
Deploy chaincode equivalent of EvidenceRegistry
IPFS Integration
Store encrypted files off-chain:
Upload *.enc to IPFS
Store CID (content hash) on-chain instead of SHA-256
Web UI
Add Flask/FastAPI interface:
Upload evidence through the browser
View verification status dashboard
Download audit reports

# License
MIT License - See LICENSE file for details.



---
