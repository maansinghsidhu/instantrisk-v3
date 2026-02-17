"""
InstantRisk V2 - Smart Contract Automation Service

Manages insurance policy NFTs and parametric claims on Polygon blockchain.
Uses Web3.py to interact with deployed Solidity contracts.

Architecture:
- PolicyNFT contract: ERC-721 representing insurance policies
- ParametricClaims contract: Auto-pays claims on oracle triggers
- Polygon Mumbai testnet (production: Polygon mainnet)
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============================================================
# ABI definitions (inline - no external file dependency)
# ============================================================

POLICY_NFT_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "string", "name": "policyId", "type": "string"},
            {"internalType": "uint256", "name": "premium", "type": "uint256"},
            {"internalType": "uint256", "name": "sumInsured", "type": "uint256"},
            {"internalType": "uint256", "name": "inception", "type": "uint256"},
            {"internalType": "uint256", "name": "expiry", "type": "uint256"},
        ],
        "name": "mintPolicy",
        "outputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "getPolicyData",
        "outputs": [
            {"internalType": "string", "name": "policyId", "type": "string"},
            {"internalType": "uint256", "name": "premium", "type": "uint256"},
            {"internalType": "uint256", "name": "sumInsured", "type": "uint256"},
            {"internalType": "uint256", "name": "inception", "type": "uint256"},
            {"internalType": "uint256", "name": "expiry", "type": "uint256"},
            {"internalType": "bool", "name": "active", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "cancelPolicy",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "policyId", "type": "string"}],
        "name": "getTokenByPolicyId",
        "outputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

PARAMETRIC_CLAIMS_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "string", "name": "trigger", "type": "string"},
            {"internalType": "uint256", "name": "triggerValue", "type": "uint256"},
            {"internalType": "uint256", "name": "claimAmount", "type": "uint256"},
        ],
        "name": "submitParametricClaim",
        "outputs": [{"internalType": "uint256", "name": "claimId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "claimId", "type": "uint256"}],
        "name": "getClaimStatus",
        "outputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "string", "name": "trigger", "type": "string"},
            {"internalType": "uint256", "name": "claimAmount", "type": "uint256"},
            {"internalType": "uint8", "name": "status", "type": "uint8"},
            {"internalType": "uint256", "name": "submittedAt", "type": "uint256"},
            {"internalType": "uint256", "name": "resolvedAt", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "claimId", "type": "uint256"}],
        "name": "processClaim",
        "outputs": [{"internalType": "bool", "name": "paid", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Solidity source for PolicyNFT (compiled and deployed on Polygon)
POLICY_NFT_SOLIDITY = '''
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

contract PolicyNFT is ERC721, Ownable {
    using Counters for Counters.Counter;
    Counters.Counter private _tokenIds;

    struct PolicyData {
        string policyId;
        uint256 premium;       // in wei (MATIC)
        uint256 sumInsured;    // in wei (MATIC)
        uint256 inception;     // unix timestamp
        uint256 expiry;        // unix timestamp
        bool active;
    }

    mapping(uint256 => PolicyData) public policies;
    mapping(string => uint256) public policyIdToToken;

    event PolicyMinted(uint256 indexed tokenId, string policyId, address indexed holder);
    event PolicyCancelled(uint256 indexed tokenId, string policyId);

    constructor() ERC721("InstantRisk Policy", "IRP") Ownable(msg.sender) {}

    function mintPolicy(
        address to,
        string memory policyId,
        uint256 premium,
        uint256 sumInsured,
        uint256 inception,
        uint256 expiry
    ) external onlyOwner returns (uint256) {
        require(bytes(policyId).length > 0, "Policy ID required");
        require(expiry > block.timestamp, "Policy already expired");
        require(policyIdToToken[policyId] == 0, "Policy ID already minted");

        _tokenIds.increment();
        uint256 newTokenId = _tokenIds.current();

        _safeMint(to, newTokenId);
        policies[newTokenId] = PolicyData(policyId, premium, sumInsured, inception, expiry, true);
        policyIdToToken[policyId] = newTokenId;

        emit PolicyMinted(newTokenId, policyId, to);
        return newTokenId;
    }

    function getPolicyData(uint256 tokenId) external view returns (
        string memory policyId, uint256 premium, uint256 sumInsured,
        uint256 inception, uint256 expiry, bool active
    ) {
        PolicyData memory p = policies[tokenId];
        return (p.policyId, p.premium, p.sumInsured, p.inception, p.expiry, p.active);
    }

    function getTokenByPolicyId(string memory policyId) external view returns (uint256) {
        return policyIdToToken[policyId];
    }

    function cancelPolicy(uint256 tokenId) external onlyOwner {
        require(policies[tokenId].active, "Policy already cancelled");
        policies[tokenId].active = false;
        emit PolicyCancelled(tokenId, policies[tokenId].policyId);
    }
}
'''

PARAMETRIC_CLAIMS_SOLIDITY = '''
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

interface IPolicyNFT {
    function getPolicyData(uint256 tokenId) external view returns (
        string memory, uint256, uint256, uint256, uint256, bool
    );
}

contract ParametricClaims is Ownable {
    enum ClaimStatus { Pending, Approved, Paid, Rejected }

    struct Claim {
        uint256 tokenId;
        string trigger;        // e.g. "wind_speed_mph", "earthquake_richter"
        uint256 triggerValue;  // scaled by 100 (e.g. 1250 = 12.50 mph)
        uint256 claimAmount;
        ClaimStatus status;
        uint256 submittedAt;
        uint256 resolvedAt;
    }

    IPolicyNFT public policyNFT;
    uint256 public claimCounter;
    mapping(uint256 => Claim) public claims;
    mapping(string => uint256) public triggerThresholds; // trigger -> threshold (scaled x100)

    event ClaimSubmitted(uint256 indexed claimId, uint256 indexed tokenId, string trigger, uint256 amount);
    event ClaimPaid(uint256 indexed claimId, uint256 amount);
    event ClaimRejected(uint256 indexed claimId, string reason);

    constructor(address _policyNFT) Ownable(msg.sender) {
        policyNFT = IPolicyNFT(_policyNFT);
        // Default parametric triggers
        triggerThresholds["wind_speed_mph"] = 7400;    // 74.00 mph (hurricane category 1)
        triggerThresholds["earthquake_richter"] = 600; // 6.00 richter
        triggerThresholds["rainfall_mm"] = 15000;      // 150.00 mm / 24h
        triggerThresholds["flood_depth_cm"] = 10000;   // 100.00 cm
    }

    function submitParametricClaim(
        uint256 tokenId,
        string memory trigger,
        uint256 triggerValue,
        uint256 claimAmount
    ) external returns (uint256) {
        (, , uint256 sumInsured, , uint256 expiry, bool active) = policyNFT.getPolicyData(tokenId);
        require(active, "Policy not active");
        require(block.timestamp <= expiry, "Policy expired");
        require(claimAmount <= sumInsured, "Claim exceeds sum insured");
        require(triggerThresholds[trigger] > 0, "Unknown trigger type");
        require(triggerValue >= triggerThresholds[trigger], "Trigger threshold not met");

        claimCounter++;
        claims[claimCounter] = Claim(
            tokenId, trigger, triggerValue, claimAmount,
            ClaimStatus.Approved, block.timestamp, 0
        );

        emit ClaimSubmitted(claimCounter, tokenId, trigger, claimAmount);
        return claimCounter;
    }

    function getClaimStatus(uint256 claimId) external view returns (
        uint256 tokenId, string memory trigger, uint256 claimAmount,
        uint8 status, uint256 submittedAt, uint256 resolvedAt
    ) {
        Claim memory c = claims[claimId];
        return (c.tokenId, c.trigger, c.claimAmount, uint8(c.status), c.submittedAt, c.resolvedAt);
    }

    function processClaim(uint256 claimId) external onlyOwner returns (bool) {
        Claim storage c = claims[claimId];
        require(c.status == ClaimStatus.Approved, "Claim not in approved state");
        c.status = ClaimStatus.Paid;
        c.resolvedAt = block.timestamp;
        emit ClaimPaid(claimId, c.claimAmount);
        return true;
    }

    function setTriggerThreshold(string memory trigger, uint256 threshold) external onlyOwner {
        triggerThresholds[trigger] = threshold;
    }

    receive() external payable {}
}
'''


# ============================================================
# Data classes
# ============================================================

@dataclass
class BlockchainConfig:
    """Polygon network configuration."""
    rpc_url: str
    chain_id: int
    policy_nft_address: Optional[str]
    parametric_claims_address: Optional[str]
    operator_private_key: Optional[str]
    gas_limit: int = 500000
    max_fee_gwei: int = 50


@dataclass
class PolicyMintResult:
    """Result of minting a policy NFT."""
    success: bool
    token_id: Optional[int] = None
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    error: Optional[str] = None
    simulated: bool = False


@dataclass
class ClaimResult:
    """Result of submitting a parametric claim."""
    success: bool
    claim_id: Optional[int] = None
    tx_hash: Optional[str] = None
    status: str = "pending"
    payout_amount: Optional[float] = None
    error: Optional[str] = None
    simulated: bool = False


# ============================================================
# Smart Contract Service
# ============================================================

class SmartContractService:
    """
    Manages insurance policies on the Polygon blockchain.

    In simulation mode (no Web3 installed or no RPC configured):
    - Returns realistic mock responses for all operations
    - Stores state in memory for the session

    In live mode:
    - Connects to Polygon via RPC
    - Signs transactions with operator private key
    - Tracks gas costs
    """

    CLAIM_STATUS_MAP = {0: "pending", 1: "approved", 2: "paid", 3: "rejected"}

    def __init__(self):
        self.config = self._load_config()
        self.w3 = None
        self.policy_nft = None
        self.parametric_claims = None
        self._simulation_mode = True
        self._sim_token_counter = 1000
        self._sim_claim_counter = 100
        self._sim_policies: Dict[str, Any] = {}
        self._sim_claims: Dict[int, Any] = {}
        self._initialized = False

    def _load_config(self) -> BlockchainConfig:
        """Load blockchain config from environment."""
        return BlockchainConfig(
            rpc_url=os.getenv("POLYGON_RPC_URL", "https://rpc-mumbai.maticvigil.com"),
            chain_id=int(os.getenv("POLYGON_CHAIN_ID", "80001")),  # 80001=Mumbai, 137=mainnet
            policy_nft_address=os.getenv("POLICY_NFT_ADDRESS"),
            parametric_claims_address=os.getenv("PARAMETRIC_CLAIMS_ADDRESS"),
            operator_private_key=os.getenv("POLYGON_OPERATOR_KEY"),
            gas_limit=int(os.getenv("POLYGON_GAS_LIMIT", "500000")),
            max_fee_gwei=int(os.getenv("POLYGON_MAX_FEE_GWEI", "50")),
        )

    async def initialize(self) -> bool:
        """
        Initialize Web3 connection and contract instances.
        Falls back to simulation mode if Web3 unavailable.
        """
        if self._initialized:
            return not self._simulation_mode

        try:
            from web3 import Web3
            from web3.middleware import geth_poa_middleware

            w3 = Web3(Web3.HTTPProvider(self.config.rpc_url, request_kwargs={"timeout": 30}))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # Required for Polygon

            if not w3.is_connected():
                raise ConnectionError(f"Cannot connect to {self.config.rpc_url}")

            self.w3 = w3
            logger.info(f"Web3 connected to chain {w3.eth.chain_id}")

            # Load contract instances if addresses configured
            if self.config.policy_nft_address:
                self.policy_nft = w3.eth.contract(
                    address=Web3.to_checksum_address(self.config.policy_nft_address),
                    abi=POLICY_NFT_ABI,
                )
            if self.config.parametric_claims_address:
                self.parametric_claims = w3.eth.contract(
                    address=Web3.to_checksum_address(self.config.parametric_claims_address),
                    abi=PARAMETRIC_CLAIMS_ABI,
                )

            self._simulation_mode = False
            logger.info("Smart contract service: LIVE mode (Polygon)")

        except ImportError:
            logger.warning("web3 package not installed - running in simulation mode")
            self._simulation_mode = True
        except Exception as e:
            logger.warning(f"Blockchain connection failed ({e}) - running in simulation mode")
            self._simulation_mode = True

        self._initialized = True
        return not self._simulation_mode

    async def get_network_info(self) -> Dict[str, Any]:
        """Return current network info."""
        await self.initialize()
        if self._simulation_mode:
            return {
                "mode": "simulation",
                "network": "Polygon Mumbai (simulated)",
                "chain_id": self.config.chain_id,
                "rpc_url": self.config.rpc_url,
                "policy_nft_deployed": bool(self.config.policy_nft_address),
                "parametric_claims_deployed": bool(self.config.parametric_claims_address),
                "contracts": {
                    "policy_nft": self.config.policy_nft_address or "Not deployed",
                    "parametric_claims": self.config.parametric_claims_address or "Not deployed",
                },
                "note": "Set POLYGON_RPC_URL, POLICY_NFT_ADDRESS, PARAMETRIC_CLAIMS_ADDRESS, POLYGON_OPERATOR_KEY env vars to enable live mode",
            }

        try:
            latest_block = self.w3.eth.block_number
            gas_price_gwei = self.w3.from_wei(self.w3.eth.gas_price, "gwei")
            return {
                "mode": "live",
                "network": "Polygon Mainnet" if self.config.chain_id == 137 else "Polygon Mumbai Testnet",
                "chain_id": self.config.chain_id,
                "latest_block": latest_block,
                "gas_price_gwei": float(gas_price_gwei),
                "policy_nft": self.config.policy_nft_address,
                "parametric_claims": self.config.parametric_claims_address,
            }
        except Exception as e:
            return {"mode": "live", "error": str(e)}

    async def issue_policy_nft(
        self,
        assessment_id: str,
        policy_id: str,
        holder_wallet: str,
        premium_matic: float,
        sum_insured_matic: float,
        inception_ts: int,
        expiry_ts: int,
    ) -> PolicyMintResult:
        """
        Mint a PolicyNFT on Polygon for a given assessment.

        Args:
            assessment_id: InstantRisk assessment UUID
            policy_id: Human-readable policy reference (e.g. IRP-2026-001)
            holder_wallet: Insured's Polygon wallet address (0x...)
            premium_matic: Premium in MATIC tokens
            sum_insured_matic: Sum insured in MATIC tokens
            inception_ts: Unix timestamp for policy start
            expiry_ts: Unix timestamp for policy end

        Returns:
            PolicyMintResult with token_id and tx_hash
        """
        await self.initialize()

        if self._simulation_mode:
            return await self._simulate_mint(
                policy_id, holder_wallet, premium_matic, sum_insured_matic, inception_ts, expiry_ts
            )

        try:
            from web3 import Web3

            # Validate inputs
            if not Web3.is_address(holder_wallet):
                return PolicyMintResult(success=False, error=f"Invalid wallet: {holder_wallet}")
            if not self.policy_nft:
                return PolicyMintResult(success=False, error="PolicyNFT contract not deployed")
            if not self.config.operator_private_key:
                return PolicyMintResult(success=False, error="Operator private key not configured")

            operator = self.w3.eth.account.from_key(self.config.operator_private_key)
            nonce = self.w3.eth.get_transaction_count(operator.address)

            # Build transaction
            tx = self.policy_nft.functions.mintPolicy(
                Web3.to_checksum_address(holder_wallet),
                policy_id,
                self.w3.to_wei(premium_matic, "ether"),
                self.w3.to_wei(sum_insured_matic, "ether"),
                inception_ts,
                expiry_ts,
            ).build_transaction({
                "chainId": self.config.chain_id,
                "gas": self.config.gas_limit,
                "maxFeePerGas": self.w3.to_wei(self.config.max_fee_gwei, "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei(2, "gwei"),
                "nonce": nonce,
            })

            # Sign and send
            signed = self.w3.eth.account.sign_transaction(tx, self.config.operator_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                # Extract token ID from logs
                token_id = self._extract_token_id_from_receipt(receipt)
                logger.info(f"Policy NFT minted: token={token_id} tx={tx_hash.hex()}")
                return PolicyMintResult(
                    success=True,
                    token_id=token_id,
                    tx_hash=tx_hash.hex(),
                    block_number=receipt.blockNumber,
                    gas_used=receipt.gasUsed,
                )
            else:
                return PolicyMintResult(success=False, error="Transaction reverted")

        except Exception as e:
            logger.error(f"Policy mint failed: {e}")
            return PolicyMintResult(success=False, error=str(e))

    async def _simulate_mint(
        self,
        policy_id: str,
        holder_wallet: str,
        premium_matic: float,
        sum_insured_matic: float,
        inception_ts: int,
        expiry_ts: int,
    ) -> PolicyMintResult:
        """Simulate minting in memory for demo/testing."""
        self._sim_token_counter += 1
        token_id = self._sim_token_counter
        tx_hash = f"0x{'a' * 64}"[:66]

        self._sim_policies[policy_id] = {
            "token_id": token_id,
            "policy_id": policy_id,
            "holder": holder_wallet,
            "premium_matic": premium_matic,
            "sum_insured_matic": sum_insured_matic,
            "inception": inception_ts,
            "expiry": expiry_ts,
            "active": True,
            "minted_at": datetime.now(timezone.utc).isoformat(),
        }

        await asyncio.sleep(0.1)  # Simulate block time
        logger.info(f"[SIM] Policy NFT minted: token={token_id} policy={policy_id}")
        return PolicyMintResult(
            success=True,
            token_id=token_id,
            tx_hash=tx_hash,
            block_number=45_000_000 + token_id,
            gas_used=185_000,
            simulated=True,
        )

    async def get_policy_on_chain(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Fetch policy data from blockchain by policy ID."""
        await self.initialize()

        if self._simulation_mode:
            pol = self._sim_policies.get(policy_id)
            if not pol:
                return None
            return {**pol, "source": "simulation"}

        try:
            if not self.policy_nft:
                return None
            token_id = self.policy_nft.functions.getTokenByPolicyId(policy_id).call()
            if token_id == 0:
                return None
            data = self.policy_nft.functions.getPolicyData(token_id).call()
            return {
                "token_id": token_id,
                "policy_id": data[0],
                "premium_wei": data[1],
                "sum_insured_wei": data[2],
                "inception": data[3],
                "expiry": data[4],
                "active": data[5],
                "source": "blockchain",
            }
        except Exception as e:
            logger.error(f"get_policy_on_chain error: {e}")
            return None

    async def submit_parametric_claim(
        self,
        policy_id: str,
        trigger_type: str,
        trigger_value: float,
        claim_amount_matic: float,
    ) -> ClaimResult:
        """
        Submit a parametric insurance claim.

        Args:
            policy_id: Policy reference ID
            trigger_type: Event type (wind_speed_mph, earthquake_richter, rainfall_mm, flood_depth_cm)
            trigger_value: Observed event value
            claim_amount_matic: Claim payout in MATIC

        Returns:
            ClaimResult with claim_id and status
        """
        await self.initialize()

        if self._simulation_mode:
            return await self._simulate_claim(policy_id, trigger_type, trigger_value, claim_amount_matic)

        try:
            if not self.parametric_claims:
                return ClaimResult(success=False, error="ParametricClaims contract not deployed")
            if not self.config.operator_private_key:
                return ClaimResult(success=False, error="Operator private key not configured")

            # Get token ID
            token_id = self.policy_nft.functions.getTokenByPolicyId(policy_id).call()
            if token_id == 0:
                return ClaimResult(success=False, error=f"Policy {policy_id} not found on chain")

            from web3 import Web3
            operator = self.w3.eth.account.from_key(self.config.operator_private_key)
            nonce = self.w3.eth.get_transaction_count(operator.address)

            # Trigger value scaled x100 (avoid floats in Solidity)
            trigger_scaled = int(trigger_value * 100)
            claim_wei = self.w3.to_wei(claim_amount_matic, "ether")

            tx = self.parametric_claims.functions.submitParametricClaim(
                token_id, trigger_type, trigger_scaled, claim_wei
            ).build_transaction({
                "chainId": self.config.chain_id,
                "gas": self.config.gas_limit,
                "maxFeePerGas": self.w3.to_wei(self.config.max_fee_gwei, "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei(2, "gwei"),
                "nonce": nonce,
            })

            signed = self.w3.eth.account.sign_transaction(tx, self.config.operator_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                claim_id = self._extract_claim_id_from_receipt(receipt)
                return ClaimResult(
                    success=True,
                    claim_id=claim_id,
                    tx_hash=tx_hash.hex(),
                    status="approved",
                    payout_amount=claim_amount_matic,
                )
            else:
                return ClaimResult(success=False, error="Transaction reverted - trigger threshold not met?")

        except Exception as e:
            logger.error(f"Parametric claim failed: {e}")
            return ClaimResult(success=False, error=str(e))

    async def _simulate_claim(
        self,
        policy_id: str,
        trigger_type: str,
        trigger_value: float,
        claim_amount_matic: float,
    ) -> ClaimResult:
        """Simulate parametric claim in memory."""
        # Check policy exists
        pol = self._sim_policies.get(policy_id)
        if not pol:
            return ClaimResult(success=False, error=f"Policy {policy_id} not found (not minted yet)")
        if not pol["active"]:
            return ClaimResult(success=False, error="Policy is cancelled")

        # Check parametric triggers
        thresholds = {
            "wind_speed_mph": 74.0,
            "earthquake_richter": 6.0,
            "rainfall_mm": 150.0,
            "flood_depth_cm": 100.0,
        }
        threshold = thresholds.get(trigger_type)
        if threshold is None:
            return ClaimResult(success=False, error=f"Unknown trigger type: {trigger_type}. Valid: {list(thresholds)}")
        if trigger_value < threshold:
            return ClaimResult(
                success=False,
                error=f"Trigger threshold not met: {trigger_value} < {threshold} ({trigger_type})",
            )

        if claim_amount_matic > pol["sum_insured_matic"]:
            return ClaimResult(success=False, error="Claim amount exceeds sum insured")

        self._sim_claim_counter += 1
        claim_id = self._sim_claim_counter

        self._sim_claims[claim_id] = {
            "claim_id": claim_id,
            "policy_id": policy_id,
            "token_id": pol["token_id"],
            "trigger_type": trigger_type,
            "trigger_value": trigger_value,
            "claim_amount_matic": claim_amount_matic,
            "status": "approved",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
        }

        await asyncio.sleep(0.1)
        return ClaimResult(
            success=True,
            claim_id=claim_id,
            tx_hash=f"0x{'b' * 64}"[:66],
            status="approved",
            payout_amount=claim_amount_matic,
            simulated=True,
        )

    async def get_claim_status(self, claim_id: int) -> Optional[Dict[str, Any]]:
        """Get parametric claim status."""
        await self.initialize()

        if self._simulation_mode:
            claim = self._sim_claims.get(claim_id)
            if not claim:
                return None
            return {**claim, "source": "simulation"}

        try:
            if not self.parametric_claims:
                return None
            data = self.parametric_claims.functions.getClaimStatus(claim_id).call()
            return {
                "claim_id": claim_id,
                "token_id": data[0],
                "trigger": data[1],
                "claim_amount_wei": data[2],
                "status": self.CLAIM_STATUS_MAP.get(data[3], "unknown"),
                "submitted_at": data[4],
                "resolved_at": data[5],
                "source": "blockchain",
            }
        except Exception as e:
            logger.error(f"get_claim_status error: {e}")
            return None

    async def process_claim(self, claim_id: int) -> Dict[str, Any]:
        """Mark a claim as paid (operator only)."""
        await self.initialize()

        if self._simulation_mode:
            claim = self._sim_claims.get(claim_id)
            if not claim:
                return {"success": False, "error": f"Claim {claim_id} not found"}
            if claim["status"] != "approved":
                return {"success": False, "error": f"Claim status is {claim['status']}, not approved"}
            claim["status"] = "paid"
            claim["resolved_at"] = datetime.now(timezone.utc).isoformat()
            return {"success": True, "claim_id": claim_id, "status": "paid", "simulated": True}

        try:
            if not self.parametric_claims:
                return {"success": False, "error": "Contract not deployed"}
            operator = self.w3.eth.account.from_key(self.config.operator_private_key)
            nonce = self.w3.eth.get_transaction_count(operator.address)

            tx = self.parametric_claims.functions.processClaim(claim_id).build_transaction({
                "chainId": self.config.chain_id,
                "gas": 200000,
                "maxFeePerGas": self.w3.to_wei(self.config.max_fee_gwei, "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei(2, "gwei"),
                "nonce": nonce,
            })
            signed = self.w3.eth.account.sign_transaction(tx, self.config.operator_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return {"success": receipt.status == 1, "tx_hash": tx_hash.hex(), "claim_id": claim_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def cancel_policy(self, policy_id: str) -> Dict[str, Any]:
        """Cancel/deactivate a policy NFT."""
        await self.initialize()

        if self._simulation_mode:
            pol = self._sim_policies.get(policy_id)
            if not pol:
                return {"success": False, "error": f"Policy {policy_id} not found"}
            pol["active"] = False
            return {"success": True, "policy_id": policy_id, "status": "cancelled", "simulated": True}

        try:
            if not self.policy_nft:
                return {"success": False, "error": "Contract not deployed"}
            token_id = self.policy_nft.functions.getTokenByPolicyId(policy_id).call()
            if token_id == 0:
                return {"success": False, "error": "Policy not found on chain"}

            operator = self.w3.eth.account.from_key(self.config.operator_private_key)
            nonce = self.w3.eth.get_transaction_count(operator.address)
            tx = self.policy_nft.functions.cancelPolicy(token_id).build_transaction({
                "chainId": self.config.chain_id,
                "gas": 100000,
                "maxFeePerGas": self.w3.to_wei(self.config.max_fee_gwei, "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei(2, "gwei"),
                "nonce": nonce,
            })
            signed = self.w3.eth.account.sign_transaction(tx, self.config.operator_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return {"success": receipt.status == 1, "tx_hash": tx_hash.hex(), "policy_id": policy_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _extract_token_id_from_receipt(self, receipt) -> int:
        """Extract minted token ID from transaction receipt logs."""
        try:
            for log in receipt.logs:
                if self.policy_nft and log.address.lower() == self.config.policy_nft_address.lower():
                    token_id = int(log.topics[1].hex(), 16)
                    return token_id
        except Exception:
            pass
        return receipt.blockNumber  # Fallback

    def _extract_claim_id_from_receipt(self, receipt) -> int:
        """Extract claim ID from transaction receipt logs."""
        try:
            for log in receipt.logs:
                if self.parametric_claims and log.address.lower() == self.config.parametric_claims_address.lower():
                    claim_id = int(log.topics[1].hex(), 16)
                    return claim_id
        except Exception:
            pass
        return self._sim_claim_counter

    def get_solidity_contracts(self) -> Dict[str, str]:
        """Return Solidity source for deployment."""
        return {
            "PolicyNFT.sol": POLICY_NFT_SOLIDITY,
            "ParametricClaims.sol": PARAMETRIC_CLAIMS_SOLIDITY,
        }

    def get_deploy_instructions(self) -> str:
        """Return deployment instructions."""
        return """
Deploy to Polygon Mumbai Testnet:
1. Install: pip install web3 py-solc-x
2. Get MATIC from faucet: https://faucet.polygon.technology/
3. Set env vars:
   POLYGON_RPC_URL=https://rpc-mumbai.maticvigil.com
   POLYGON_CHAIN_ID=80001
   POLYGON_OPERATOR_KEY=0x<your_private_key>
4. Deploy PolicyNFT.sol first
5. Deploy ParametricClaims.sol with PolicyNFT address as constructor arg
6. Set:
   POLICY_NFT_ADDRESS=0x<deployed_address>
   PARAMETRIC_CLAIMS_ADDRESS=0x<deployed_address>
"""


# Singleton
_smart_contract_service: Optional[SmartContractService] = None


def get_smart_contract_service() -> SmartContractService:
    """Get or create the SmartContractService singleton."""
    global _smart_contract_service
    if _smart_contract_service is None:
        _smart_contract_service = SmartContractService()
    return _smart_contract_service
