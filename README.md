git clone https://github.com/Xdfighter97/evidence-chain-prototype.git
cd evidence-chain-prototype

**Blockchain-backed digital evidence integrity system** for forensic chain-of-custody.
 
   This prototype demonstrates how to:
   - Hash evidence files with cryptographic integrity (SHA-256)
   - Encrypt evidence using authenticated encryption (ChaCha20-Poly1305)
   - Anchor ciphertext hashes on an Ethereum blockchain (Ganache devnet)
   - Verify evidence has not been tampered with  

## The Architecture
 
<img width="705" height="433" alt="image" src="https://github.com/user-attachments/assets/e72a3e1b-46c6-4d2a-8cc3-611d01a02cfa" />



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
Directory Structure

<img width="382" height="502" alt="image" src="https://github.com/user-attachments/assets/b434cd5a-8e3f-454a-8148-ecaafa0d1b02" />

Step-by-Step Manual Workflow
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

Output Files
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

Reset for Fresh Run

# Clean all outputs (preserves evidence, scripts, config)
.\reset.ps1

# Keep logs
.\reset.ps1 -KeepLogs

Security Notes
Requirement	Implementation
Key Storage	Environment variable, never in repo
Key Generation	Cryptographically secure (os.urandom)
Encryption	ChaCha20-Poly1305 with unique nonce per file
Integrity	SHA-256 of ciphertext anchored on-chain
Audit Trail	Append-only timestamped logs with test IDs

Future Extensions
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

Upload evidence through browser
View verification status dashboard
Download audit reports

License
MIT License - See LICENSE file for details.



---
