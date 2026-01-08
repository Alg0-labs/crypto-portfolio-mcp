

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Chain:
  
    id: int
    name: str
    symbol: str
    explorer: str
    moralis_id: str 



CHAINS: Dict[str, Chain] = {
    "ethereum": Chain(
        id=1,
        name="Ethereum",
        symbol="ETH",
        explorer="https://etherscan.io",
        moralis_id="eth"
    ),
    "base": Chain(
        id=199,
        name="Base",
        symbol="ETH",
        explorer="https://basescan.org",
        moralis_id="base"
    ),
    "solana": Chain(
        id=16,
        name="Solana",
        symbol="SOL",
        explorer="https://solscan.io",
        moralis_id="solana"
    ),
    "polygon": Chain(
        id=25,
        name="Polygon",
        symbol="MATIC",
        explorer="https://polygonscan.com",
        moralis_id="polygon"
    ),
    "arbitrum": Chain(
        id=51,
        name="Arbitrum",
        symbol="ETH",
        explorer="https://arbiscan.io",
        moralis_id="arbitrum"
    ),
    "optimism": Chain(
        id=42,
        name="Optimism",
        symbol="ETH",
        explorer="https://optimistic.etherscan.io",
        moralis_id="optimism"

    ),
    "avalanche": Chain(
        id=28,
        name="Avalanche C-Chain",
        symbol="AVAX",
        explorer="https://snowtrace.io",
        moralis_id="avalanche"
    ),
    "bnb": Chain(
        id=14,
        name="BNB Chain",
        symbol="BNB",
        explorer="https://bscscan.com",
        moralis_id="bsc"
    ),
}


def get_chain(chain_name: str) -> Optional[Chain]:
   
    return CHAINS.get(chain_name.lower())


def get_chain_by_id(platform_id: int) -> Optional[Chain]:
    
    for chain in CHAINS.values():
        if chain.id == platform_id:
            return chain
    return None


def list_supported_chains() -> List[str]:
   
    return sorted(CHAINS.keys())


def validate_chain(chain_name: str) -> str:
   
    normalized = chain_name.lower().strip()
    if normalized not in CHAINS:
        supported = ", ".join(list_supported_chains())
        raise ValueError(
            f"Unsupported chain '{chain_name}'. "
            f"Supported chains: {supported}"
        )
    return normalized


__all__ = [
    "Chain",
    "CHAINS",
    "get_chain",
    "get_chain_by_id",
    "list_supported_chains",
    "validate_chain",
]
