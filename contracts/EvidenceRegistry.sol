// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title EvidenceRegistry
/// @notice Minimal, auditable registry for anchoring evidence ciphertext hashes.
///         Stores SHA-256(ciphertext) as bytes32, a short metadata string, and block/timestamp.
/// @dev For prototype simplicity:
///      - Uses the hash as the key; assumes uniqueness.
///      - Does not implement access control (add Ownable/roles later).
contract EvidenceRegistry {
    struct Record {
        bool exists;
        uint256 timestamp;     // block timestamp
        uint256 blockNumber;   // block number
        string metadata;       // small pointer string: case id, examiner id, etc.
    }

    mapping(bytes32 => Record) private records;

    event EvidenceRegistered(bytes32 indexed evidenceHash, string metadata, uint256 timestamp, uint256 blockNumber);

    /// @notice Register a ciphertext SHA-256 hash on-chain.
    /// @param evidenceHash bytes32 SHA-256(ciphertext)
    /// @param metadata short string (case id, examiner id, pointer). Keep it small.
    function registerEvidence(bytes32 evidenceHash, string calldata metadata) external {
        require(evidenceHash != bytes32(0), "hash=0");
        require(!records[evidenceHash].exists, "already-registered");

        records[evidenceHash] = Record({
            exists: true,
            timestamp: block.timestamp,
            blockNumber: block.number,
            metadata: metadata
        });

        emit EvidenceRegistered(evidenceHash, metadata, block.timestamp, block.number);
    }

    /// @notice Retrieve a record by ciphertext hash.
    /// @param evidenceHash bytes32 SHA-256(ciphertext)
    /// @return exists whether it exists
    /// @return timestamp stored timestamp
    /// @return blockNumber stored block number
    /// @return metadata stored metadata string
    function getEvidence(bytes32 evidenceHash)
        external
        view
        returns (bool exists, uint256 timestamp, uint256 blockNumber, string memory metadata)
    {
        Record memory r = records[evidenceHash];
        return (r.exists, r.timestamp, r.blockNumber, r.metadata);
    }
}
