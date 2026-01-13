
from typing import Dict, List, Any, Optional



def format_price(price: float, decimals: int = 6) -> str:

    if price >= 1:
       
        return f"${price:,.2f}"
    else:
        
        return f"${price:.{decimals}f}"


def format_market_cap(value: float) -> str:
    
    
    if value >= 1_000_000_000:
        
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
       
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        
        return f"${value / 1_000:.2f}K"
    else:
        
        return f"${value:.2f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def format_supply(supply: float, max_supply: Optional[float] = None) -> str:
    
    
    formatted = f"{supply:,.0f}"
    
    
    if max_supply and max_supply > 0:
        percentage = (supply / max_supply) * 100
        formatted += f" ({percentage:.1f}% of {max_supply:,.0f})"
    
    return formatted




def format_token_info(token: Dict) -> Dict[str, Any]:
    
  
    quotes = token.get("quotes", [{}])[0]
    
    
    return {
        
        "name": token.get("name"),
        "symbol": token.get("symbol"),
        "rank": token.get("cmcRank"),
        
        
        "price": format_price(quotes.get("price", 0)),
        "price_raw": quotes.get("price", 0), 
        
        
        "market_cap": format_market_cap(quotes.get("marketCap", 0)),
        "volume_24h": format_market_cap(quotes.get("volume24h", 0)),
        "volume_7d": format_market_cap(quotes.get("volume7d", 0)),
        
        
        "change_1h": format_percentage(quotes.get("percentChange1h", 0)),
        "change_24h": format_percentage(quotes.get("percentChange24h", 0)),
        "change_7d": format_percentage(quotes.get("percentChange7d", 0)),
        "change_30d": format_percentage(quotes.get("percentChange30d", 0)),
        
        
        "ath": format_price(token.get("ath", 0)),  # All-time high
        "atl": format_price(token.get("atl", 0)),  # All-time low
        "high_24h": format_price(token.get("high24h", 0)),
        "low_24h": format_price(token.get("low24h", 0)),
        
       
        "circulating_supply": f"{token.get('circulatingSupply', 0):,.0f}",
        "total_supply": f"{token.get('totalSupply', 0):,.0f}",
        "max_supply": f"{token.get('maxSupply', 0):,.0f}" if token.get("maxSupply") else "∞",
    }


def format_token_list(tokens: List[Dict]) -> List[Dict]:
    
    formatted = []
    
    for token in tokens:
        
        quotes = token.get("quotes", [{}])[0]
        
        
        formatted.append({
            "rank": token.get("cmcRank"),
            "symbol": token.get("symbol"),
            "name": token.get("name"),
            "price": format_price(quotes.get("price", 0)),
            "change_24h": format_percentage(quotes.get("percentChange24h", 0)),
            "volume_24h": format_market_cap(quotes.get("volume24h", 0)),
            "market_cap": format_market_cap(quotes.get("marketCap", 0)),
        })
    
    return formatted


def format_comparison(tokens: List[Dict]) -> Dict[str, Any]:
    
    comparison = {
        "tokens": [],
        "summary": {}
    }
    
    
    total_mcap = 0
    total_vol = 0
    best_perf = None  
    worst_perf = None
    
    
    for token in tokens:
        
        formatted = format_token_info(token)
        quotes = token.get("quotes", [{}])[0]
        
        
        comparison["tokens"].append({
            "symbol": formatted["symbol"],
            "name": formatted["name"],
            "price": formatted["price"],
            "market_cap": formatted["market_cap"],
            "volume_24h": formatted["volume_24h"],
            "change_24h": formatted["change_24h"],
            "change_7d": formatted["change_7d"],
        })
        
        
        mcap = quotes.get("marketCap", 0)
        vol = quotes.get("volume24h", 0)
        change = quotes.get("percentChange24h", 0)
        
        total_mcap += mcap
        total_vol += vol
        
        
        if best_perf is None or change > best_perf[1]:
            best_perf = (formatted["symbol"], change)
        
        
        if worst_perf is None or change < worst_perf[1]:
            worst_perf = (formatted["symbol"], change)
    
    
    comparison["summary"] = {
        "total_market_cap": format_market_cap(total_mcap),
        "total_volume_24h": format_market_cap(total_vol),
        "best_performer": f"{best_perf[0]} ({format_percentage(best_perf[1])})" if best_perf else None,
        "worst_performer": f"{worst_perf[0]} ({format_percentage(worst_perf[1])})" if worst_perf else None,
    }
    
    return comparison


def format_analytics(token: Dict, timeframe: str = "24h") -> Dict[str, Any]:
    
    quotes = token.get("quotes", [{}])[0]
    
    
    timeframe_map = {
        "1h": "percentChange1h",
        "24h": "percentChange24h",
        "7d": "percentChange7d",
        "30d": "percentChange30d",
    }
    
    
    change_key = timeframe_map.get(timeframe, "percentChange24h")
    price_change = quotes.get(change_key, 0)
    
    
    current_price = quotes.get("price", 0)
    ath = token.get("ath", 1)  
    
   
    distance_from_ath = ((current_price / ath) - 1) * 100 if ath > 0 else 0
    
    
    return {
        "symbol": token.get("symbol"),
        "name": token.get("name"),
        "timeframe": timeframe,
        
       
        "price_change": format_percentage(price_change),
        "current_price": format_price(current_price),
        "ath": format_price(ath),
        "distance_from_ath": format_percentage(distance_from_ath),
        
        
        "volume_24h": format_market_cap(quotes.get("volume24h", 0)),
        "volume_7d": format_market_cap(quotes.get("volume7d", 0)),
        
        
        "rank": token.get("cmcRank"),
        "market_cap": format_market_cap(quotes.get("marketCap", 0)),
    }



__all__ = [
   
    "format_price",
    "format_market_cap",
    "format_percentage",
    "format_supply",
    "format_token_info",
    "format_token_list",
    "format_comparison",
    "format_analytics",
]