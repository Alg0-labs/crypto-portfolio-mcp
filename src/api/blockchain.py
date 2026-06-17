

import httpx
import logging
import os
from typing import Dict, List, Optional, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


class BlockchainAPIError(Exception):
    
    pass


class MoralisClient:
    
    
    
    CHAIN_MAP = {
        "ethereum": "eth",
        "base": "base",
        "polygon": "polygon",
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "avalanche": "avalanche",
        "bnb": "bsc",
        "solana": "solana",
    }
    
    BASE_URL = "https://deep-index.moralis.io/api/v2.2"
    
    def __init__(self, api_key: str = "", timeout: int = 30):

        self.timeout = timeout
        # Default/fallback key, used in local (stdio) mode. In remote (HTTP)
        # mode each request supplies its own key via get_wallet_balances(api_key=...),
        # so an empty default here is fine and is NOT an error.
        self.api_key = api_key or os.getenv("MORALIS_API_KEY", "")

        default_headers = {"accept": "application/json"}
        if self.api_key:
            default_headers["X-API-Key"] = self.api_key

        self.session = httpx.AsyncClient(
            timeout=timeout,
            headers=default_headers,
        )

        logger.info("Moralis client initialized")
    
    async def close(self):
        
        await self.session.aclose()
    
    def _get_chain_id(self, chain: str) -> str:
        
        chain_id = self.CHAIN_MAP.get(chain.lower())
        if not chain_id:
            raise BlockchainAPIError(
                f"Unsupported chain: {chain}. "
                f"Supported: {', '.join(self.CHAIN_MAP.keys())}"
            )
        return chain_id
    
    async def get_wallet_balances(
        self,
        chain: str,
        address: str,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:

        chain_id = self._get_chain_id(chain)


        url = f"{self.BASE_URL}/wallets/{address}/tokens"

        params = {"chain": chain_id}

        # Per-request key (remote multi-user mode) overrides the client default.
        key = api_key or self.api_key
        if not key:
            raise BlockchainAPIError(
                "No Moralis API key provided. Set MORALIS_API_KEY locally, or "
                "send your own key in the 'X-Moralis-Key' request header when "
                "using the hosted server."
            )
        request_headers = {"X-API-Key": key}

        try:
            response = await self.session.get(url, params=params, headers=request_headers)
            response.raise_for_status()
            data = response.json()
            
            
            result = self._parse_wallet_response(data, address, chain)
            
            logger.info(
                f"Fetched wallet {address[:10]}... on {chain}: "
                f"${result['total_usd_value']:.2f} total value"
            )
            
            return result
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise BlockchainAPIError("Invalid Moralis API key")
            elif e.response.status_code == 429:
                raise BlockchainAPIError("Rate limit exceeded.")
            else:
                raise BlockchainAPIError(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching wallet data: {e}")
            raise BlockchainAPIError(f"Failed to fetch wallet data: {str(e)}")
    
    def _parse_wallet_response(
        self,
        data: Dict,
        address: str,
        chain: str
    ) -> Dict[str, Any]:
      
        result = {
            "address": address,
            "chain": chain,
            "total_usd_value": 0.0,
            "native": {},
            "tokens": []
        }
        
        
        tokens_list = data.get("result", [])
        
        if not tokens_list:
            logger.warning(f"No tokens found for {address} on {chain}")
            return result
        
        
        total_value = sum(
            token.get("usd_value", 0) or 0 
            for token in tokens_list
        )
        result["total_usd_value"] = total_value
        
        
        for token_data in tokens_list:
            is_native = token_data.get("native_token", False)
            
            
            if token_data.get("possible_spam", False):
                logger.debug(f"Skipping spam token: {token_data.get('symbol')}")
                continue
            
            
            usd_value = token_data.get("usd_value", 0) or 0
            if usd_value == 0:
                logger.debug(f"Skipping token with no value: {token_data.get('symbol')}")
                continue
            
            token_info = {
                "symbol": token_data.get("symbol", "UNKNOWN"),
                "name": token_data.get("name", "Unknown Token"),
                "balance": float(token_data.get("balance_formatted", 0)),
                "usd_value": usd_value,
                "usd_price": token_data.get("usd_price", 0) or 0,
                "change_24h": token_data.get("usd_price_24hr_percent_change", 0) or 0,
                "contract": token_data.get("token_address", ""),
                "logo": token_data.get("logo") or token_data.get("thumbnail"),
                "verified": token_data.get("verified_contract", False),
                "possible_spam": token_data.get("possible_spam", False),
                "portfolio_percentage": token_data.get("portfolio_percentage", 0) or 0,
                "security_score": token_data.get("security_score"),
            }
            
            if is_native:
                result["native"] = token_info
            else:
                result["tokens"].append(token_info)
        
        
        result["tokens"].sort(key=lambda x: x["usd_value"], reverse=True)
        
        return result
    
    async def get_portfolio_networth(
        self,
        address: str,
        chains: List[str]
    ) -> Dict[str, Any]:
       
        
        chain_ids = [self._get_chain_id(c) for c in chains]
        
        url = f"{self.BASE_URL}/wallets/{address}/net-worth"
        params = {"chains": ",".join(chain_ids)}
        
        try:
            response = await self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            logger.info(
                f"Portfolio net worth for {address[:10]}: "
                f"${data.get('total_networth_usd', 0):,.2f}"
            )
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching net worth: {e}")
            raise BlockchainAPIError(f"Failed to fetch net worth: {str(e)}")
    
    async def get_token_price(
        self,
        chain: str,
        token_addresses: List[str]
    ) -> Dict[str, Dict]:
       
        chain_id = self._get_chain_id(chain)
        
        url = f"{self.BASE_URL}/erc20/prices"
        params = {
            "chain": chain_id,
            "include": "percent_change"
        }
        
        
        body = {"tokens": [{"token_address": addr} for addr in token_addresses]}
        
        try:
            response = await self.session.post(url, params=params, json=body)
            response.raise_for_status()
            data = response.json()
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching token prices: {e}")
            return {}



BlockchainClient = MoralisClient


__all__ = ["MoralisClient", "BlockchainClient", "BlockchainAPIError"]