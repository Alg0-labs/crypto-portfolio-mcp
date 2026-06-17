"""
HTTP wrapper for stdio-based MCP server.
Exposes all 12 MCP tools as HTTP endpoints.

Complete production-ready version with proper MCP initialization and response parsing.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
import asyncio
import json
import logging
import sys
import os

# Set to DEBUG to see detailed logs, INFO for production
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================
# MCP Client (Complete with Initialization)
# ============================================

class MCPClient:
    """Client to communicate with MCP stdio server"""
    
    def __init__(self):
        self.process = None
        self.request_id = 0
        self.lock = asyncio.Lock()
        self.initialized = False
    
    async def start(self):
        """Start MCP server process"""
        if self.process:
            return
        
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            
            logger.info(f"Starting MCP server from: {parent_dir}")
            
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m", "src.server",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=parent_dir
            )
            
            # Wait for server to start
            await asyncio.sleep(2)
            
            # Check if process is still running
            if self.process.returncode is not None:
                stderr = await self.process.stderr.read()
                raise Exception(f"MCP server failed to start: {stderr.decode()}")
            
            logger.info(f"✅ MCP server started (PID: {self.process.pid})")
            
            # Initialize MCP session
            await self._initialize()
            
        except Exception as e:
            logger.error(f"❌ Failed to start MCP server: {e}")
            raise
    
    async def _initialize(self):
        """Initialize MCP session"""
        try:
            logger.info("Initializing MCP session...")
            
            # Send initialization request
            init_request = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "http-wrapper",
                        "version": "1.0.0"
                    }
                }
            }
            
            # Send init request
            request_json = json.dumps(init_request) + "\n"
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()
            
            # Read init response
            response_line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=10.0
            )
            
            if response_line:
                init_response = json.loads(response_line.decode())
                logger.info(f"Init response: {init_response}")
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            notification_json = json.dumps(initialized_notification) + "\n"
            self.process.stdin.write(notification_json.encode())
            await self.process.stdin.drain()
            
            self.initialized = True
            logger.info("✅ MCP session initialized")
            
        except Exception as e:
            logger.error(f"❌ MCP initialization failed: {e}")
            raise
    
    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call MCP tool via JSON-RPC"""
        async with self.lock:
            if not self.process or self.process.returncode is not None:
                logger.warning("MCP server not running, restarting...")
                await self.start()
            
            if not self.initialized:
                logger.warning("MCP not initialized, initializing...")
                await self._initialize()
            
            try:
                self.request_id += 1
                
                # JSON-RPC request
                request = {
                    "jsonrpc": "2.0",
                    "id": self.request_id,
                    "method": "tools/call",
                    "params": {
                        "name": name,
                        "arguments": arguments
                    }
                }
                
                logger.info(f"📤 Calling: {name} (id: {self.request_id})")
                logger.debug(f"Request: {json.dumps(request, indent=2)}")
                
                # Send request
                request_json = json.dumps(request) + "\n"
                self.process.stdin.write(request_json.encode())
                await self.process.stdin.drain()
                
                # Read response with timeout
                try:
                    response_line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    logger.error("⏱️  Timeout waiting for MCP response")
                    raise Exception("MCP server timeout - no response in 30s")
                
                if not response_line:
                    stderr = await self._read_stderr()
                    raise Exception(f"MCP server closed connection. Stderr: {stderr}")
                
                response_str = response_line.decode().strip()
                logger.debug(f"Raw response: {response_str}")
                
                response = json.loads(response_str)
                logger.debug(f"Parsed response keys: {response.keys()}")
                
                # Handle error
                if "error" in response:
                    error_msg = response["error"].get("message", "Unknown error")
                    error_code = response["error"].get("code", 0)
                    logger.error(f"❌ MCP error [{error_code}]: {error_msg}")
                    
                    stderr = await self._read_stderr()
                    if stderr:
                        logger.error(f"MCP stderr: {stderr}")
                    
                    raise Exception(f"MCP error: {error_msg}")
                
                # Extract result - Handle multiple response formats
                if "result" not in response:
                    raise Exception(f"No result in response: {response}")
                
                result = response["result"]
                logger.debug(f"Result type: {type(result)}, value: {str(result)[:200]}")
                
                # Parse result based on format
                result_text = self._extract_text_from_result(result)
                
                logger.info(f"✅ Success: {name}")
                logger.debug(f"Result preview: {result_text[:200]}...")
                
                return result_text
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error: {e}")
                logger.error(f"Response: {response_str if 'response_str' in locals() else 'N/A'}")
                raise Exception(f"Invalid JSON response: {e}")
            
            except Exception as e:
                logger.error(f"❌ MCP call error ({name}): {e}")
                stderr = await self._read_stderr()
                if stderr:
                    logger.error(f"MCP stderr: {stderr}")
                raise
    
    def _extract_text_from_result(self, result: Any) -> str:
        """
        Extract text from MCP result in various formats.
        
        Handles:
        - [{"type": "text", "text": "..."}]
        - {"content": [{"type": "text", "text": "..."}]}
        - {"text": "..."}
        - Plain strings
        """
        # Format 1: List of content items
        if isinstance(result, list):
            if len(result) > 0:
                first_item = result[0]
                
                # [{"type": "text", "text": "..."}]
                if isinstance(first_item, dict):
                    if "text" in first_item:
                        return first_item["text"]
                    else:
                        return str(first_item)
                
                # Plain list
                else:
                    return str(result)
            else:
                return ""
        
        # Format 2: Dict with content
        elif isinstance(result, dict):
            # {"content": [...]}
            if "content" in result:
                content = result["content"]
                
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]
                    
                    if isinstance(first_content, dict) and "text" in first_content:
                        return first_content["text"]
                    else:
                        return str(first_content)
                
                else:
                    return str(content)
            
            # {"text": "..."}
            elif "text" in result:
                return result["text"]
            
            # Unknown dict format
            else:
                logger.warning(f"Unknown dict result format: {result.keys()}")
                return json.dumps(result, indent=2)
        
        # Format 3: Plain string
        elif isinstance(result, str):
            return result
        
        # Fallback: Convert to string
        else:
            logger.warning(f"Unknown result type: {type(result)}")
            return str(result)
    
    async def _read_stderr(self) -> str:
        """Read stderr for debugging"""
        if self.process and self.process.stderr:
            try:
                stderr = await asyncio.wait_for(
                    self.process.stderr.read(2048),
                    timeout=1.0
                )
                return stderr.decode() if stderr else ""
            except:
                return ""
        return ""
    
    async def close(self):
        """Close MCP server process"""
        if self.process:
            try:
                logger.info("Terminating MCP server...")
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("MCP server didn't terminate, killing...")
                self.process.kill()
                await self.process.wait()
            logger.info("MCP server stopped")


# Global MCP client
mcp: Optional[MCPClient] = None


# ============================================
# Lifespan Event Handler
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler"""
    global mcp
    
    # Startup
    logger.info("="*60)
    logger.info("🚀 Starting HTTP Wrapper for MCP Server")
    logger.info("="*60)
    
    try:
        mcp = MCPClient()
        await mcp.start()
        logger.info("✅ HTTP Wrapper ready to accept requests")
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise
    
    yield
    
    # Shutdown
    if mcp:
        await mcp.close()
        logger.info("👋 HTTP Wrapper stopped")


# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="Crypto Trading Agents - MCP API",
    description="HTTP wrapper for MCP server with 12 crypto analysis tools",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Pydantic Models
# ============================================

class ToolCallRequest(BaseModel):
    """Generic tool call request"""
    name: str = Field(..., description="Tool name")
    arguments: Dict[str, Any] = Field(..., description="Tool arguments")


class ToolCallResponse(BaseModel):
    """Generic tool call response"""
    success: bool
    result: str
    error: Optional[str] = None


class MarketMetricsRequest(BaseModel):
    """Get market metrics request"""
    symbols: List[str] = Field(..., min_length=1, max_length=20)
    chain: Optional[str] = None


class CompareTokensRequest(BaseModel):
    """Compare tokens request"""
    symbols: List[str] = Field(..., min_length=2, max_length=10)
    chain: Optional[str] = None


class CompareChainsRequest(BaseModel):
    """Compare chains request"""
    chains: List[str] = Field(..., min_length=2, max_length=5)
    limit: int = Field(default=10, ge=1, le=50)


# ============================================
# Root & Health Endpoints
# ============================================

@app.get("/")
async def root():
    """API root - show status and available endpoints"""
    return {
        "service": "Crypto Trading Agents - MCP API",
        "version": "1.0.0",
        "status": "running",
        "initialized": mcp.initialized if mcp else False,
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc",
            "market": "/api/v1/market/...",
            "portfolio": "/api/v1/portfolio/...",
            "tools": "/api/v1/tools/call"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    is_running = mcp and mcp.process and mcp.process.returncode is None
    return {
        "status": "healthy" if (is_running and mcp.initialized) else "unhealthy",
        "mcp_running": is_running,
        "mcp_initialized": mcp.initialized if mcp else False,
        "mcp_pid": mcp.process.pid if (mcp and mcp.process) else None,
        "tools_available": 12
    }


# ============================================
# Generic Tool Call Endpoint
# ============================================

@app.post("/api/v1/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """
    Call any MCP tool via HTTP.
    
    Example:
        POST /api/v1/tools/call
        {
            "name": "get_token_info",
            "arguments": {"symbol": "ETH"}
        }
    """
    try:
        result = await mcp.call_tool(request.name, request.arguments)
        return ToolCallResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return ToolCallResponse(success=False, result="", error=str(e))


# ============================================
# Market Data Endpoints (8 tools)
# ============================================

@app.get("/api/v1/market/token/{symbol}")
async def get_token_info(symbol: str, chain: Optional[str] = Query(None)):
    """
    Get comprehensive token information.
    
    Args:
        symbol: Token symbol (e.g., BTC, ETH, SOL)
        chain: Optional blockchain filter
    """
    try:
        args = {"symbol": symbol}
        if chain:
            args["chain"] = chain
        
        result = await mcp.call_tool("get_token_info", args)
        return {"success": True, "symbol": symbol, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/market/tokens/{chain}")
async def list_tokens(
    chain: str,
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("volume_24h")
):
    """
    List top tokens on a blockchain.
    
    Args:
        chain: Blockchain name (ethereum, base, solana, etc.)
        limit: Number of tokens (1-100)
        sort_by: Sort field (volume_24h or market_cap)
    """
    try:
        result = await mcp.call_tool("list_tokens", {
            "chain": chain,
            "limit": limit,
            "sort_by": sort_by
        })
        return {"success": True, "chain": chain, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/market/metrics")
async def get_market_metrics(request: MarketMetricsRequest):
    """
    Get market metrics for multiple tokens.
    
    Body:
        {
            "symbols": ["BTC", "ETH", "SOL"],
            "chain": "ethereum"  // optional
        }
    """
    try:
        args = {"symbols": request.symbols}
        if request.chain:
            args["chain"] = request.chain
        
        result = await mcp.call_tool("get_market_metrics", args)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/market/analytics/{symbol}")
async def get_token_analytics(
    symbol: str,
    timeframe: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    chain: Optional[str] = Query(None)
):
    """
    Get token analytics over a timeframe.
    
    Args:
        symbol: Token symbol
        timeframe: Analysis period (1h, 24h, 7d, 30d)
        chain: Optional blockchain filter
    """
    try:
        args = {"symbol": symbol, "timeframe": timeframe}
        if chain:
            args["chain"] = chain
        
        result = await mcp.call_tool("get_token_analytics", args)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/market/compare/tokens")
async def compare_tokens(request: CompareTokensRequest):
    """
    Compare multiple tokens side-by-side.
    
    Body:
        {
            "symbols": ["BTC", "ETH", "SOL"],
            "chain": "ethereum"  // optional
        }
    """
    try:
        args = {"symbols": request.symbols}
        if request.chain:
            args["chain"] = request.chain
        
        result = await mcp.call_tool("compare_tokens", args)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/market/chains")
async def list_chains():
    """List all supported blockchain networks."""
    try:
        result = await mcp.call_tool("list_chains", {})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/market/compare/chains")
async def compare_chains(request: CompareChainsRequest):
    """
    Compare blockchain ecosystems.
    
    Body:
        {
            "chains": ["ethereum", "base", "solana"],
            "limit": 10
        }
    """
    try:
        result = await mcp.call_tool("compare_chains", {
            "chains": request.chains,
            "limit": request.limit
        })
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/market/search/{symbol}")
async def search_token(symbol: str):
    """
    Search for a token across all chains.
    
    Args:
        symbol: Token symbol to search
    """
    try:
        result = await mcp.call_tool("search_token_across_chains", {"symbol": symbol})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Portfolio Endpoints (4 tools)
# ============================================

@app.get("/api/v1/portfolio/analyze/{address}")
async def analyze_wallet(address: str, chain: str = Query(...)):
    """
    Analyze a crypto wallet's portfolio.
    
    Args:
        address: Wallet address
        chain: Blockchain name
    """
    try:
        result = await mcp.call_tool("analyze_wallet", {
            "address": address,
            "chain": chain
        })
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/portfolio/recommendations/{address}")
async def get_recommendations(address: str, chain: str = Query(...)):
    """
    Get AI-powered portfolio recommendations.
    
    Args:
        address: Wallet address
        chain: Blockchain name
    """
    try:
        result = await mcp.call_tool("get_portfolio_recommendations", {
            "address": address,
            "chain": chain
        })
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/portfolio/vs-market/{address}")
async def compare_to_market(address: str, chain: str = Query(...)):
    """
    Compare portfolio performance to market averages.
    
    Args:
        address: Wallet address
        chain: Blockchain name
    """
    try:
        result = await mcp.call_tool("compare_portfolio_to_market", {
            "address": address,
            "chain": chain
        })
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/portfolio/summary/{address}")
async def get_summary(address: str, chain: str = Query(...)):
    """
    Get quick portfolio summary.
    
    Args:
        address: Wallet address
        chain: Blockchain name
    """
    try:
        result = await mcp.call_tool("get_portfolio_summary", {
            "address": address,
            "chain": chain
        })
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Run Server
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    print("="*60)
    print("🚀 Crypto Trading Agents - MCP HTTP Wrapper")
    print("="*60)
    print(f"📡 Server: http://localhost:6274")
    print(f"📚 Docs: http://localhost:6274/docs")
    print(f"🔍 Health: http://localhost:6274/health")
    print("="*60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=6274,
        log_level="info"
    )