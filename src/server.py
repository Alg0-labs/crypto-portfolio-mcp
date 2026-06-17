

import asyncio
import logging
import os
from typing import Any
from dotenv import load_dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .api.coinmarketcap import CoinMarketCapClient, CoinMarketCapAPIError
from .api.blockchain import MoralisClient, BlockchainAPIError
from .utils.formatters import (
    format_token_info,
    format_token_list,
    format_comparison,
    format_analytics,
    format_market_cap,
)
from .utils.validators import (
    validate_symbol,
    validate_symbols,
    validate_limit,
    validate_timeframe,
    validate_wallet_address,
    ValidationError,
)
from .utils.chains import (
    CHAINS,
    get_chain,
    get_chain_by_id,
    list_supported_chains,
    validate_chain,
)
from .utils.portfolio import (
    PortfolioAnalyzer,
)


load_dotenv()


logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("coinmarketcap-mcp")


server = Server("coinmarketcap-mcp")


api_client: CoinMarketCapClient = None
blockchain_client: MoralisClient = None
portfolio_analyzer: PortfolioAnalyzer = None


def _get_moralis_key() -> str:
    """Resolve the caller's Moralis API key.

    Remote (HTTP) mode: read it from the per-request 'X-Moralis-Key' header
    (or 'Authorization: Bearer <key>'), so each user brings their own key.
    Local (stdio) mode: fall back to the MORALIS_API_KEY environment variable.
    Returns "" if none is available; the caller surfaces a clear error.
    """
    request = None
    try:
        request = server.request_context.request
    except LookupError:
        request = None

    if request is not None:  # remote HTTP transport carries the Starlette request
        header_key = request.headers.get("X-Moralis-Key")
        if not header_key:
            auth = request.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                header_key = auth[7:].strip()
        if header_key:
            return header_key

    return os.getenv("MORALIS_API_KEY", "")


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    
    
    supported_chains = ", ".join(list_supported_chains())
    
    return [
       
        
        Tool(
            name="get_token_info",
            description=f"""Get comprehensive information about a cryptocurrency token.
            
            
            Supported chains: {supported_chains}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Token symbol (e.g., WETH, SOL, MATIC)",
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Blockchain name ({supported_chains})",
                    },
                },
                "required": ["symbol"],
            },
        ),
        
        Tool(
            name="list_tokens",
            description=f"""List top cryptocurrency tokens on any blockchain network.
            
            Supported chains: {supported_chains}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "chain": {
                        "type": "string",
                        "description": f"Blockchain name ({supported_chains})",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of tokens (1-100, default: 20)",
                        "default": 20,
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort field",
                        "default": "volume_24h",
                        "enum": ["volume_24h", "market_cap"],
                    },
                },
                "required": ["chain"],
            },
        ),
        
        Tool(
            name="get_market_metrics",
            description="Fetch market metrics for one or more tokens.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of token symbols",
                        "minItems": 1,
                        "maxItems": 20,
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Filter by chain ({supported_chains})",
                    },
                },
                "required": ["symbols"],
            },
        ),
        
        Tool(
            name="get_token_analytics",
            description="Get analytical insights about a token's performance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Token symbol to analyze",
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "Analysis period",
                        "enum": ["1h", "24h", "7d", "30d"],
                        "default": "24h",
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Blockchain name ({supported_chains})",
                    },
                },
                "required": ["symbol"],
            },
        ),
        
        Tool(
            name="compare_tokens",
            description="Compare multiple tokens side-by-side.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-10 token symbols to compare",
                        "minItems": 2,
                        "maxItems": 10,
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Filter by chain ({supported_chains})",
                    },
                },
                "required": ["symbols"],
            },
        ),
        
        Tool(
            name="list_chains",
            description="""List all supported blockchain networks.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        
        Tool(
            name="compare_chains",
            description="Compare token ecosystems across multiple blockchains.",
            inputSchema={
                "type": "object",
                "properties": {
                    "chains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"2-5 chain names ({supported_chains})",
                        "minItems": 2,
                        "maxItems": 5,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Tokens per chain to analyze",
                        "default": 10,
                    },
                },
                "required": ["chains"],
            },
        ),
        
        Tool(
            name="search_token_across_chains",
            description="Search for a token across all supported blockchains.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Token symbol to search for",
                    },
                },
                "required": ["symbol"],
            },
        ),
        
        
        
        Tool(
            name="analyze_wallet",
            description="""Analyze a crypto wallet's complete portfolio.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Wallet address",
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Blockchain name ({supported_chains})",
                        "enum": list(CHAINS.keys()),
                    },
                },
                "required": ["address", "chain"],
            },
        ),
        
        Tool(
            name="get_portfolio_recommendations",
            description="""Get AI-powered recommendations for your portfolio.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Wallet address",
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Blockchain name ({supported_chains})",
                        "enum": list(CHAINS.keys()),
                    },
                },
                "required": ["address", "chain"],
            },
        ),
        
        Tool(
            name="compare_portfolio_to_market",
            description="""Compare your portfolio performance to market averages.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Wallet address",
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Blockchain name ({supported_chains})",
                        "enum": list(CHAINS.keys()),
                    },
                },
                "required": ["address", "chain"],
            },
        ),
        
        Tool(
            name="get_portfolio_summary",
            description="""Get a quick summary of a wallet's portfolio.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Wallet address",
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Blockchain name ({supported_chains})",
                        "enum": list(CHAINS.keys()),
                    },
                },
                "required": ["address", "chain"],
            },
        ),
    ]


# ============================================================================
# TOOL CALL ROUTER
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    
    try:
        logger.info(f"Tool called: {name}")
        
        
        if name == "get_token_info":
            result = await handle_get_token_info(arguments)
        elif name == "list_tokens":
            result = await handle_list_tokens(arguments)
        elif name == "get_market_metrics":
            result = await handle_get_market_metrics(arguments)
        elif name == "get_token_analytics":
            result = await handle_get_token_analytics(arguments)
        elif name == "compare_tokens":
            result = await handle_compare_tokens(arguments)
        elif name == "list_chains":
            result = await handle_list_chains(arguments)
        elif name == "compare_chains":
            result = await handle_compare_chains(arguments)
        elif name == "search_token_across_chains":
            result = await handle_search_token_across_chains(arguments)
        
        
        elif name == "analyze_wallet":
            result = await handle_analyze_wallet(arguments)
        elif name == "get_portfolio_recommendations":
            result = await handle_get_portfolio_recommendations(arguments)
        elif name == "compare_portfolio_to_market":
            result = await handle_compare_portfolio_to_market(arguments)
        elif name == "get_portfolio_summary":
            result = await handle_get_portfolio_summary(arguments)
        
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        return [TextContent(type="text", text=result)]
        
    except (ValidationError, ValueError) as e:
        logger.warning(f"Validation error in {name}: {e}")
        return [TextContent(type="text", text=f"Invalid input: {str(e)}")]
    except (CoinMarketCapAPIError, BlockchainAPIError) as e:
        logger.error(f"API error in {name}: {e}")
        return [TextContent(type="text", text=f"API error: {str(e)}")]
    except Exception as e:
        logger.error(f"Unexpected error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"An error occurred: {str(e)}")]


# ============================================================================
# MARKET DATA TOOL HANDLERS
# ============================================================================

async def handle_get_token_info(args: dict) -> str:
    
    symbol = validate_symbol(args["symbol"])
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    token = await api_client.get_token_by_symbol(symbol, platform_id)
    
    if not token:
        chain_msg = f" on {chain_name}" if chain_name else ""
        return f"Token '{symbol}' not found{chain_msg}. Try a different chain or check the symbol."
    
    info = format_token_info(token)
    
    chain_display = ""
    if chain_name:
        chain = get_chain(chain_name)
        chain_display = f"\n**Chain:** {chain.name} ({chain.symbol})\n**Explorer:** {chain.explorer}"
    
    return f"""# {info['name']} ({info['symbol']}){chain_display}

**Rank:** #{info['rank']}

## Current Price
- **Price:** {info['price']}
- **24h High:** {info['high_24h']}
- **24h Low:** {info['low_24h']}
- **All-Time High:** {info['ath']}
- **All-Time Low:** {info['atl']}

## Market Data
- **Market Cap:** {info['market_cap']}
- **Volume 24h:** {info['volume_24h']}
- **Volume 7d:** {info['volume_7d']}

## Price Changes
- **1 Hour:** {info['change_1h']}
- **24 Hours:** {info['change_24h']}
- **7 Days:** {info['change_7d']}
- **30 Days:** {info['change_30d']}

## Supply
- **Circulating:** {info['circulating_supply']}
- **Total:** {info['total_supply']}
- **Max:** {info['max_supply']}
"""


async def handle_list_tokens(args: dict) -> str:
    
    chain_name = validate_chain(args["chain"])
    limit = validate_limit(args.get("limit", 20), max_val=100)
    sort_by = args.get("sort_by", "volume_24h")
    
    chain = get_chain(chain_name)
    
    tokens = await api_client.get_cryptocurrency_listing(
        limit=limit,
        sort_by=sort_by,
        platform_id=chain.id
    )
    
    if not tokens:
        return f"No tokens found on {chain.name}."
    
    formatted = format_token_list(tokens)
    
    result = f"# Top {len(formatted)} Tokens on {chain.name}\n\n"
    result += f"**Chain:** {chain.name} ({chain.symbol})\n"
    result += f"**Explorer:** {chain.explorer}\n"
    result += f"**Sorted by:** {sort_by}\n\n"
    result += "| Rank | Symbol | Name | Price | 24h Change | Volume | Market Cap |\n"
    result += "|------|--------|------|-------|------------|--------|------------|\n"
    
    for token in formatted:
        result += (
            f"| {token['rank']} | {token['symbol']} | {token['name']} | "
            f"{token['price']} | {token['change_24h']} | "
            f"{token['volume_24h']} | {token['market_cap']} |\n"
        )
    
    return result


async def handle_get_market_metrics(args: dict) -> str:
    
    symbols = validate_symbols(args["symbols"])
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    tokens = await api_client.get_multiple_tokens(symbols, platform_id)
    
    if not tokens:
        return f"No tokens found for: {', '.join(symbols)}"
    
    chain_display = f" on {chain_name}" if chain_name else ""
    result = f"# Market Metrics{chain_display}\n\n"
    
    for token in tokens:
        info = format_token_info(token)
        result += f"## {info['symbol']}\n"
        result += f"- **Price:** {info['price']} ({info['change_24h']} 24h)\n"
        result += f"- **Market Cap:** {info['market_cap']}\n"
        result += f"- **Volume 24h:** {info['volume_24h']}\n\n"
    
    return result


async def handle_get_token_analytics(args: dict) -> str:
    
    symbol = validate_symbol(args["symbol"])
    timeframe = validate_timeframe(args.get("timeframe", "24h"))
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    token = await api_client.get_token_by_symbol(symbol, platform_id)
    
    if not token:
        return f"Token '{symbol}' not found."
    
    analytics = format_analytics(token, timeframe)
    
    chain_display = ""
    if chain_name:
        chain = get_chain(chain_name)
        chain_display = f"\n**Chain:** {chain.name}"
    
    return f"""# {analytics['name']} ({analytics['symbol']}) Analytics{chain_display}

**Analysis Period:** {analytics['timeframe']}

## Performance
- **Price Change:** {analytics['price_change']}
- **Current Price:** {analytics['current_price']}
- **All-Time High:** {analytics['ath']}
- **Distance from ATH:** {analytics['distance_from_ath']}

## Volume
- **24h Volume:** {analytics['volume_24h']}
- **7d Volume:** {analytics['volume_7d']}

## Market Position
- **CMC Rank:** #{analytics['rank']}
- **Market Cap:** {analytics['market_cap']}
"""


async def handle_compare_tokens(args: dict) -> str:
    
    symbols = validate_symbols(args["symbols"])
    
    if len(symbols) < 2:
        raise ValidationError("Need at least 2 tokens to compare")
    if len(symbols) > 10:
        raise ValidationError("Maximum 10 tokens allowed")
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    tokens = await api_client.get_multiple_tokens(symbols, platform_id)
    
    if not tokens:
        return f"No tokens found for: {', '.join(symbols)}"
    
    comparison = format_comparison(tokens)
    
    chain_display = f" on {chain_name}" if chain_name else ""
    result = f"# Token Comparison{chain_display}\n\n"
    result += "| Symbol | Name | Price | Market Cap | Volume 24h | Change 24h | Change 7d |\n"
    result += "|--------|------|-------|------------|------------|------------|----------|\n"
    
    for token in comparison['tokens']:
        result += (
            f"| {token['symbol']} | {token['name']} | {token['price']} | "
            f"{token['market_cap']} | {token['volume_24h']} | "
            f"{token['change_24h']} | {token['change_7d']} |\n"
        )
    
    result += f"\n## Summary\n"
    result += f"- **Combined Market Cap:** {comparison['summary']['total_market_cap']}\n"
    result += f"- **Combined Volume:** {comparison['summary']['total_volume_24h']}\n"
    result += f"- **Best Performer:** {comparison['summary']['best_performer']}\n"
    result += f"- **Worst Performer:** {comparison['summary']['worst_performer']}\n"
    
    return result


async def handle_list_chains(args: dict) -> str:
    """List all supported chains."""
    result = "# Supported Blockchain Networks\n\n"
    result += "| Chain | Native Token | Platform ID | Explorer |\n"
    result += "|-------|--------------|-------------|----------|\n"
    
    for chain_name in sorted(CHAINS.keys()):
        chain = CHAINS[chain_name]
        result += (
            f"| {chain.name} | {chain.symbol} | "
            f"{chain.id} | [Link]({chain.explorer}) |\n"
        )
    
    result += f"\n**Total Chains:** {len(CHAINS)}\n"
    result += f"\n**Available chains:** {', '.join(sorted(CHAINS.keys()))}\n"
    
    return result


async def handle_compare_chains(args: dict) -> str:
    
    chain_names = [validate_chain(c) for c in args["chains"]]
    
    if len(chain_names) < 2:
        raise ValidationError("Need at least 2 chains to compare")
    if len(chain_names) > 5:
        raise ValidationError("Maximum 5 chains allowed")
    
    limit = validate_limit(args.get("limit", 10), max_val=50)
    
    result = "# Blockchain Ecosystem Comparison\n\n"
    
    chain_stats = []
    
    for chain_name in chain_names:
        chain = get_chain(chain_name)
        
        tokens = await api_client.get_cryptocurrency_listing(
            limit=limit,
            platform_id=chain.id
        )
        
        if tokens:
            total_mcap = sum(
                t.get("quotes", [{}])[0].get("marketCap", 0) 
                for t in tokens
            )
            total_vol = sum(
                t.get("quotes", [{}])[0].get("volume24h", 0) 
                for t in tokens
            )
            top_token = tokens[0] if tokens else None
            
            chain_stats.append({
                "name": chain.name,
                "symbol": chain.symbol,
                "token_count": len(tokens),
                "total_mcap": format_market_cap(total_mcap),
                "total_vol": format_market_cap(total_vol),
                "top_token": top_token.get("symbol") if top_token else "N/A",
                "explorer": chain.explorer,
            })
    
    result += "| Chain | Native | Tokens | Total Market Cap | Total Volume | Top Token | Explorer |\n"
    result += "|-------|--------|--------|------------------|--------------|-----------|----------|\n"
    
    for stats in chain_stats:
        result += (
            f"| {stats['name']} | {stats['symbol']} | "
            f"{stats['token_count']} | {stats['total_mcap']} | "
            f"{stats['total_vol']} | {stats['top_token']} | "
            f"[Link]({stats['explorer']}) |\n"
        )
    
    return result


async def handle_search_token_across_chains(args: dict) -> str:
    
    symbol = validate_symbol(args["symbol"])
    
    result = f"# Cross-Chain Search: {symbol}\n\n"
    
    found_tokens = []
    
    for chain_name, chain in CHAINS.items():
        token = await api_client.get_token_by_symbol(symbol, chain.id)
        
        if token:
            info = format_token_info(token)
            found_tokens.append({
                "chain": chain.name,
                "chain_key": chain_name,
                "symbol": chain.symbol,
                "price": info['price'],
                "price_raw": info['price_raw'],
                "volume": info['volume_24h'],
                "market_cap": info['market_cap'],
                "explorer": chain.explorer,
            })
    
    if not found_tokens:
        return f"Token '{symbol}' not found on any supported chain."
    
    result += f"**Found on {len(found_tokens)} chain(s):**\n\n"
    result += "| Chain | Native | Price | Volume 24h | Market Cap | Explorer |\n"
    result += "|-------|--------|-------|------------|------------|----------|\n"
    
    for token in found_tokens:
        result += (
            f"| {token['chain']} | {token['symbol']} | "
            f"{token['price']} | {token['volume']} | "
            f"{token['market_cap']} | [Link]({token['explorer']}) |\n"
        )
    
    if len(found_tokens) > 1:
        prices = [t['price_raw'] for t in found_tokens]
        highest = max(prices)
        lowest = min(prices)
        diff_pct = ((highest - lowest) / lowest) * 100 if lowest > 0 else 0
        
        result += f"\n## Price Analysis\n"
        result += f"- **Highest Price:** ${highest:,.6f}\n"
        result += f"- **Lowest Price:** ${lowest:,.6f}\n"
        result += f"- **Price Difference:** {diff_pct:.2f}%\n"
    
    return result


# ============================================================================
# PORTFOLIO TOOL HANDLERS 
# ============================================================================

async def handle_analyze_wallet(args: dict) -> str:
    
    address = validate_wallet_address(args["address"], args["chain"])
    chain = validate_chain(args["chain"])
    
    
    logger.info(f"Fetching balances for {address[:10]}... on {chain}")
    wallet_data = await blockchain_client.get_wallet_balances(chain, address, api_key=_get_moralis_key())
    
    
    total_value = wallet_data.get("total_usd_value", 0)
    
    if total_value == 0:
        return f"# Wallet Analysis: {address[:10]}...{address[-8:]}\n\n**Status:** Empty wallet - No holdings with value found."
    
    
    analysis = portfolio_analyzer.analyze_portfolio(wallet_data)
    
    
    summary = analysis["summary"]
    holdings = analysis["holdings"]
    allocation = analysis["allocation"]
    risk = analysis["risk"]
    performance = analysis["performance"]
    insights = analysis["insights"]
    
    result = f"""# Portfolio Analysis: {address[:10]}...{address[-8:]}

**Chain:** {chain.title()}
**Total Value:** ${summary['total_value']:,.2f}
**Holdings:** {summary['total_holdings']} assets

---

## Holdings

| Asset | Balance | Price | Value | Allocation | 24h Change |
|-------|---------|-------|-------|------------|------------|
"""
    
    for holding in holdings:
        verified_badge = "Verified" if holding.get("verified") else ""
        result += (
            f"| {holding['symbol']} {verified_badge} | {holding['balance']:.4f} | "
            f"${holding['price']:.2f} | ${holding['value']:,.2f} | "
            f"{holding['allocation']:.1f}% | {holding['change_24h']:+.2f}% |\n"
        )
    
    result += f"""
---

## Asset Allocation

- **Diversification Score:** {allocation['diversification_score']}/100
- **Top 3 Holdings:** {allocation['top_3_percentage']:.1f}% of portfolio
- **Concentration Level:** {allocation['concentration']}

### Top Holdings:
"""
    
    for i, holding in enumerate(allocation['top_holdings'], 1):
        result += f"{i}. **{holding['symbol']}** - {holding['allocation']:.1f}% (${holding['value']:,.2f})\n"
    
    result += f"""
---

## Risk Assessment

- **Risk Level:** {risk['level']}
- **Risk Score:** {risk['score']}/100

"""
    
    if risk['factors']:
        result += "**Risk Factors:**\n"
        for factor in risk['factors']:
            result += f"- {factor}\n"
    
    result += f"""
---

## Performance (24h)

- **Portfolio Change:** {performance['total_change_24h']:+.2f}%
- **Winners:** {performance['winners_count']} | **Losers:** {performance['losers_count']}
"""
    
    if performance['best_performer']:
        result += f"- **Best Performer:** {performance['best_performer']['symbol']} ({performance['best_performer']['change']:+.2f}%)\n"
    
    if performance['worst_performer']:
        result += f"- **Worst Performer:** {performance['worst_performer']['symbol']} ({performance['worst_performer']['change']:+.2f}%)\n"
    
    result += "\n---\n\n## Insights\n\n"
    
    for insight in insights:
        result += f"{insight}\n\n"
    
    return result


async def handle_get_portfolio_recommendations(args: dict) -> str:
    
    address = validate_wallet_address(args["address"], args["chain"])
    chain = validate_chain(args["chain"])
    
    
    wallet_data = await blockchain_client.get_wallet_balances(chain, address, api_key=_get_moralis_key())
    
    if wallet_data.get("total_usd_value", 0) == 0:
        return f"Cannot generate recommendations for empty wallet."
    
    
    analysis = portfolio_analyzer.analyze_portfolio(wallet_data)
    
    
    recommendations = portfolio_analyzer.generate_recommendations(analysis)
    
    result = f"""# Portfolio Recommendations: {address[:10]}...{address[-8:]}

**Chain:** {chain.title()}
**Total Value:** ${analysis['summary']['total_value']:,.2f}

---

"""
    
    if not recommendations:
        result += "**Your portfolio looks well-balanced!** No immediate recommendations.\n"
    else:
        for i, rec in enumerate(recommendations, 1):
            priority_emoji = {
                "High": "RED",
                "Medium": "YELLOW",
                "Low": "GREEN"
            }.get(rec['priority'], "⚪")
            
            result += f"""## {priority_emoji} {rec['type']} ({rec['priority']} Priority)

**Action:** {rec['action']}

**Reasoning:** {rec['reasoning']}

---

"""
    
    return result


async def handle_compare_portfolio_to_market(args: dict) -> str:
    
    address = validate_wallet_address(args["address"], args["chain"])
    chain = validate_chain(args["chain"])
    
    
    wallet_data = await blockchain_client.get_wallet_balances(chain, address, api_key=_get_moralis_key())
    
    if wallet_data.get("total_usd_value", 0) == 0:
        return "Cannot compare empty wallet to market."
    
    
    analysis = portfolio_analyzer.analyze_portfolio(wallet_data)
    portfolio_change = analysis["performance"]["total_change_24h"]
    
    
    chain_obj = get_chain(chain)
    market_tokens = await api_client.get_cryptocurrency_listing(
        limit=20,
        platform_id=chain_obj.id
    )
    
    
    market_changes = []
    for token in market_tokens:
        change = token.get("quotes", [{}])[0].get("percentChange24h", 0)
        market_changes.append(change)
    
    market_avg = sum(market_changes) / len(market_changes) if market_changes else 0
    
    result = f"""# Portfolio vs Market Comparison

**Wallet:** {address[:10]}...{address[-8:]}
**Chain:** {chain.title()}

---

## 24h Performance Comparison

| Metric | Your Portfolio | Market Average | Difference |
|--------|---------------|----------------|------------|
| 24h Change | {portfolio_change:+.2f}% | {market_avg:+.2f}% | {(portfolio_change - market_avg):+.2f}% |

"""
    
    if portfolio_change > market_avg:
        result += "**Your portfolio is outperforming the market!**\n\n"
        result += f"Your portfolio is up {(portfolio_change - market_avg):.2f}% more than the average.\n"
    elif portfolio_change < market_avg:
        result += "**Your portfolio is underperforming the market.**\n\n"
        result += f"Your portfolio is down {abs(portfolio_change - market_avg):.2f}% compared to the average.\n"
    else:
        result += "**Your portfolio is tracking the market.**\n\n"
    
    result += f"""
---

## Market Context

Top performing tokens on {chain.title()} (24h):

| Rank | Symbol | 24h Change |
|------|--------|-----------|
"""
    
    sorted_tokens = sorted(
        market_tokens[:10],
        key=lambda x: x.get("quotes", [{}])[0].get("percentChange24h", 0),
        reverse=True
    )[:5]
    
    for i, token in enumerate(sorted_tokens, 1):
        change = token.get("quotes", [{}])[0].get("percentChange24h", 0)
        result += f"| {i} | {token['symbol']} | {change:+.2f}% |\n"
    
    return result


async def handle_get_portfolio_summary(args: dict) -> str:
    
    address = validate_wallet_address(args["address"], args["chain"])
    chain = validate_chain(args["chain"])
    
    
    wallet_data = await blockchain_client.get_wallet_balances(chain, address, api_key=_get_moralis_key())
    
    total_value = wallet_data.get("total_usd_value", 0)
    
    if total_value == 0:
        return f"# Portfolio Summary: {address[:10]}...{address[-8:]}\n\n**Status:** Empty wallet"
    
    
    analysis = portfolio_analyzer.analyze_portfolio(wallet_data)
    
    summary = analysis["summary"]
    holdings = analysis["holdings"][:3]  
    performance = analysis["performance"]
    
    result = f"""# Portfolio Summary: {address[:10]}...{address[-8:]}

**Chain:** {chain.title()}
**Total Value:** ${summary['total_value']:,.2f}
**Holdings:** {summary['total_holdings']} assets
**24h Change:** {performance['total_change_24h']:+.2f}%

---

## Top Holdings

"""
    
    for i, holding in enumerate(holdings, 1):
        verified_badge = "Verified" if holding.get("verified") else ""
        result += f"{i}. **{holding['symbol']}** {verified_badge} - ${holding['value']:,.2f} ({holding['allocation']:.1f}%)\n"
    
    if performance['best_performer']:
        result += f"\n**Best Performer:** {performance['best_performer']['symbol']} ({performance['best_performer']['change']:+.2f}%)\n"
    
    if performance['worst_performer']:
        result += f"**Worst Performer:** {performance['worst_performer']['symbol']} ({performance['worst_performer']['change']:+.2f}%)\n"
    
    return result


# ============================================================================
# SERVER LIFECYCLE
# ============================================================================

async def main():
    
    global api_client, blockchain_client, portfolio_analyzer
    
    
    api_client = CoinMarketCapClient(
        base_url=os.getenv("API_BASE_URL", "https://api.coinmarketcap.com/data-api/v3"),
        timeout=int(os.getenv("API_TIMEOUT", "30"))
    )
    
    
    blockchain_client = MoralisClient(timeout=30)
    
    
    portfolio_analyzer = PortfolioAnalyzer()
    
    logger.info("=" * 60)
    logger.info("CoinMarketCap MCP Server (Multi-Chain + Portfolio Edition)")
    logger.info(f"Supported Chains: {', '.join(sorted(CHAINS.keys()))}")
    logger.info(f"Total Tools: 12 (8 market + 4 portfolio)")
    logger.info("=" * 60)
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    finally:
        await api_client.close()
        await blockchain_client.close()
        logger.info("Server shutdown")


def build_http_app():
    """Build a Starlette ASGI app exposing this MCP server over Streamable HTTP.

    The MCP endpoint is mounted at /mcp. Stateless mode is used so every request
    is independent — ideal for a public, multi-user server where each caller
    brings their own Moralis API key via the 'X-Moralis-Key' header.
    """
    import contextlib
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse

    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=False,
        stateless=True,
    )

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    async def health(_request):
        return JSONResponse({"status": "ok", "server": "coinmarketcap-mcp"})

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        global api_client, blockchain_client, portfolio_analyzer

        api_client = CoinMarketCapClient(
            base_url=os.getenv("API_BASE_URL", "https://api.coinmarketcap.com/data-api/v3"),
            timeout=int(os.getenv("API_TIMEOUT", "30")),
        )
        blockchain_client = MoralisClient(timeout=30)  # per-request keys; no env key required
        portfolio_analyzer = PortfolioAnalyzer()

        async with session_manager.run():
            logger.info("=" * 60)
            logger.info("CoinMarketCap MCP Server — Streamable HTTP at /mcp")
            logger.info(f"Supported Chains: {', '.join(sorted(CHAINS.keys()))}")
            logger.info("=" * 60)
            try:
                yield
            finally:
                await api_client.close()
                await blockchain_client.close()
                logger.info("Server shutdown")

    return Starlette(
        routes=[
            Route("/health", health),
            # MCP endpoint. Requests to /mcp are 307-redirected to /mcp/, which
            # preserves the POST body, so clients may use either form.
            Mount("/mcp", app=handle_mcp),
        ],
        lifespan=lifespan,
    )


def main_http():
    """Run the server as a remote MCP server over HTTP (for hosting)."""
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        build_http_app(),
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    # MCP_TRANSPORT=http -> remote/hosted mode; otherwise local stdio mode.
    if os.getenv("MCP_TRANSPORT", "stdio").lower() == "http":
        main_http()
    else:
        asyncio.run(main())