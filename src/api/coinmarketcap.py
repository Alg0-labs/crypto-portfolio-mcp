

import httpx
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)



class CoinMarketCapAPIError(Exception):
  

    pass


class CoinMarketCapClient:
  
    
    def __init__(
        self,
        base_url: str = "https://api.coinmarketcap.com/data-api/v3",
        timeout: int = 30,
    ):
     
        
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        
        self.session = httpx.AsyncClient(
            timeout=timeout,
            headers={
                
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Referer': 'https://coinmarketcap.com'
            }
        )
        
        
        # Structure: {cache_key: (data, timestamp)}
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(seconds=60)  
        
        logger.info(f"API client initialized: {self.base_url}")
    
    async def close(self):
    
        await self.session.aclose()
        logger.info("API client closed")
    
    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """
        Generate unique cache key from endpoint and parameters.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            Unique string identifying this request
            
        """
        # Sort params to ensure consistency
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{endpoint}?{param_str}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        Retrieve data from cache if not expired.
        
        Args:
            cache_key: Unique cache identifier
            
        Returns:
            Cached data if valid, None if expired or not found
            
        """
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            
            # Check if cache is still valid
            if datetime.now() - timestamp < self._cache_ttl:
                logger.debug(f"Cache HIT: {cache_key}")
                return data
            else:
                # Cache expired, remove it
                del self._cache[cache_key]
                logger.debug(f"Cache EXPIRED: {cache_key}")
        
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    
    def _set_cache(self, cache_key: str, data: Any):
        """
        Store data in cache with current timestamp.
        
        Args:
            cache_key: Unique cache identifier
            data: Data to cache
            
        """
        self._cache[cache_key] = (data, datetime.now())
        logger.debug(f"Cache SET: {cache_key}")
    

    
    async def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> Dict:
       
        params = params or {}
        cache_key = self._get_cache_key(endpoint, params)
        
       
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"Request attempt {attempt + 1}/{max_retries}: {url}")
                
                
                response = await self.session.get(url, params=params)
                
                
                response.raise_for_status()
                
                
                data = response.json()
                
                
                if 'data' not in data:
                    raise CoinMarketCapAPIError(
                        "Invalid API response: missing 'data' field"
                    )
                
                
                self._set_cache(cache_key, data)
                
                logger.info(f"Request successful: {endpoint}")
                return data
                
            except httpx.HTTPStatusError as e:
                
                logger.error(
                    f"HTTP error on attempt {attempt + 1}: "
                    f"Status {e.response.status_code}"
                )
                
                
                if 400 <= e.response.status_code < 500:
                    raise CoinMarketCapAPIError(
                        f"Client error: {e.response.status_code}"
                    )
                
                
                if attempt == max_retries - 1:
                    
                    raise CoinMarketCapAPIError(
                        f"Server error after {max_retries} attempts: "
                        f"{e.response.status_code}"
                    )
                
                
                await asyncio.sleep(2 ** attempt)
                
            except httpx.RequestError as e:
                
                logger.error(f"Request error on attempt {attempt + 1}: {e}")
                
                if attempt == max_retries - 1:
                    raise CoinMarketCapAPIError(
                        f"Network error after {max_retries} attempts: {str(e)}"
                    )
                
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                
                if attempt == max_retries - 1:
                    raise CoinMarketCapAPIError(
                        f"Unexpected error: {str(e)}"
                    )
                
                await asyncio.sleep(2 ** attempt)
        
        
        raise CoinMarketCapAPIError("Max retries exceeded")
    
  
    
    async def get_cryptocurrency_listing(
        self,
        start: int = 1,
        limit: int = 100,
        sort_by: str = "volume_24h",
        platform_id: Optional[int] = None,
    ) -> List[Dict]:
       
        
        params = {
            "start": start,
            "limit": min(limit, 500),  
            "sortBy": sort_by,
            "sortType": "desc",
            "convert": "USD",
            "cryptoType": "all",
            "tagType": "all",
            "audited": "false",
            "aux": "ath,atl,high24h,low24h,num_market_pairs,cmc_rank,"
                   "date_added,max_supply,circulating_supply,total_supply,"
                   "volume_7d,volume_30d"
        }
        
        
        if platform_id:
            params["platformId"] = platform_id
        
        
        response = await self._make_request(
            "/cryptocurrency/listing", 
            params
        )
        
        return response.get("data", {}).get("cryptoCurrencyList", [])
    
    async def get_token_by_symbol(
        self, 
        symbol: str, 
        platform_id: Optional[int] = None
    ) -> Optional[Dict]:
       
        
        listings = await self.get_cryptocurrency_listing(
            limit=500,  
            platform_id=platform_id
        )
        
        
        symbol_upper = symbol.upper()
        for token in listings:
            if token.get("symbol", "").upper() == symbol_upper:
                logger.info(f"Found token: {symbol}")
                return token
        
        
        logger.warning(f"Token not found: {symbol}")
        return None
    
    async def get_multiple_tokens(
        self, 
        symbols: List[str], 
        platform_id: Optional[int] = None
    ) -> List[Dict]:
  
        
        listings = await self.get_cryptocurrency_listing(
            limit=500,
            platform_id=platform_id
        )
        
        
        symbols_upper = [s.upper() for s in symbols]
        
        
        results = []
        for token in listings:
            if token.get("symbol", "").upper() in symbols_upper:
                results.append(token)
        
        logger.info(
            f"Found {len(results)}/{len(symbols)} requested tokens"
        )
        return results




__all__ = [
    "CoinMarketCapClient",
    "CoinMarketCapAPIError",
]