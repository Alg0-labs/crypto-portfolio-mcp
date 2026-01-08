"""
Portfolio Analysis Module
"""

from typing import Dict, List, Any, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PortfolioAnalyzer:
   
    
    def __init__(self):
        
        logger.info("Portfolio analyzer initialized")
    
    def analyze_portfolio(
        self,
        wallet_data: Dict[str, Any],
        market_data: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, Any]:
        
        holdings = []
        total_value = wallet_data.get("total_usd_value", 0)
        
        
        native = wallet_data.get("native", {})
        if native and native.get("balance", 0) > 0:
            holdings.append({
                "symbol": native["symbol"],
                "name": native.get("name", native["symbol"]),
                "balance": native["balance"],
                "price": native.get("usd_price", 0),
                "value": native.get("usd_value", 0),
                "type": "native",
                "change_24h": native.get("change_24h", 0),
                "allocation": native.get("portfolio_percentage", 0),
                "logo": native.get("logo"),
                "verified": native.get("verified", True),
                "contract": "",
            })
        
        
        for token in wallet_data.get("tokens", []):
            holdings.append({
                "symbol": token["symbol"],
                "name": token.get("name", token["symbol"]),
                "balance": token["balance"],
                "price": token.get("usd_price", 0),
                "value": token.get("usd_value", 0),
                "type": "token",
                "contract": token.get("contract", ""),
                "change_24h": token.get("change_24h", 0),
                "allocation": token.get("portfolio_percentage", 0),
                "logo": token.get("logo"),
                "verified": token.get("verified", False),
                "security_score": token.get("security_score"),
            })
        
        
        holdings.sort(key=lambda x: x["value"], reverse=True)
        
        
        if total_value > 0:
            for holding in holdings:
                if holding.get("allocation", 0) == 0:
                    holding["allocation"] = (holding["value"] / total_value * 100)
        
        
        analysis = {
            "summary": {
                "address": wallet_data.get("address"),
                "chain": wallet_data.get("chain"),
                "total_value": total_value,
                "total_holdings": len(holdings),
            },
            "holdings": holdings,
            "allocation": self._analyze_allocation(holdings, total_value),
            "risk": self._analyze_risk(holdings, total_value),
            "performance": self._analyze_performance(holdings),
            "insights": self._generate_insights(holdings, total_value),
        }
        
        return analysis
    
    def _analyze_allocation(
        self,
        holdings: List[Dict],
        total_value: float
    ) -> Dict[str, Any]:
        
        if total_value == 0 or not holdings:
            return {
                "diversification_score": 0,
                "top_holdings": [],
                "concentration": "N/A",
                "top_3_percentage": 0,
            }
        
        
        top_holdings = holdings[:3]
        top_3_value = sum(h["value"] for h in top_holdings)
        top_3_percent = (top_3_value / total_value * 100) if total_value > 0 else 0
        
        # Diversification score (Herfindahl-Hirschman Index)
        # HHI = sum of squared market shares
        # Diversification score = (1 - HHI) * 100
        hhi = sum((h["allocation"] / 100) ** 2 for h in holdings)
        diversification_score = (1 - hhi) * 100  
        
        
        if top_3_percent > 75:
            concentration = "High"
        elif top_3_percent > 50:
            concentration = "Medium"
        else:
            concentration = "Low"
        
        return {
            "diversification_score": round(diversification_score, 2),
            "top_3_percentage": round(top_3_percent, 2),
            "concentration": concentration,
            "top_holdings": [
                {
                    "symbol": h["symbol"],
                    "name": h.get("name", h["symbol"]),
                    "allocation": round(h["allocation"], 2),
                    "value": h["value"],
                    "logo": h.get("logo"),
                }
                for h in top_holdings
            ]
        }
    
    def _analyze_risk(
        self,
        holdings: List[Dict],
        total_value: float
    ) -> Dict[str, Any]:
        
        if not holdings:
            return {
                "level": "N/A",
                "score": 0,
                "factors": []
            }
        
        risk_factors = []
        risk_score = 0
        
        
        if len(holdings) < 3:
            risk_factors.append(
                f"Low diversification: Only {len(holdings)} holding. "
                f"Consider diversifying across 3-5 different assets."
            )
            risk_score += 30
        
        
        top_holding = holdings[0] if holdings else None
        if top_holding and top_holding["allocation"] > 50:
            risk_factors.append(
                f"High concentration: {top_holding['symbol']} represents "
                f"{top_holding['allocation']:.1f}% of portfolio. "
                f"Consider rebalancing."
            )
            risk_score += 25
        
        
        volatile_holdings = [
            h for h in holdings 
            if abs(h.get("change_24h", 0)) > 10
        ]
        if len(volatile_holdings) > len(holdings) * 0.5:
            risk_factors.append(
                f"High volatility: {len(volatile_holdings)} assets with >10% daily moves. "
                f"Market may be experiencing turbulence."
            )
            risk_score += 20
        
        
        unverified = [h for h in holdings if not h.get("verified", False)]
        if len(unverified) > 0:
            risk_factors.append(
                f"Unverified contracts: {len(unverified)} token(s) not verified. "
                f"Exercise caution with unverified assets."
            )
            risk_score += 15
        
        
        low_security = [
            h for h in holdings 
            if h.get("security_score") is not None and h.get("security_score", 100) < 50
        ]
        if len(low_security) > 0:
            risk_factors.append(
                f"Security concerns: {len(low_security)} tokens have low security scores. "
                f"Review these positions carefully."
            )
            risk_score += 10
        
        
        if risk_score >= 50:
            risk_level = "High"
        elif risk_score >= 25:
            risk_level = "Medium"
        else:
            risk_level = "Low"
        
        return {
            "level": risk_level,
            "score": min(risk_score, 100),  
            "factors": risk_factors
        }
    
    def _analyze_performance(self, holdings: List[Dict]) -> Dict[str, Any]:
       
        if not holdings:
            return {
                "total_change_24h": 0,
                "best_performer": None,
                "worst_performer": None,
                "winners_count": 0,
                "losers_count": 0,
            }
        
        
        total_change = sum(
            h["value"] * h.get("change_24h", 0) / 100
            for h in holdings
        )
        total_value = sum(h["value"] for h in holdings)
        avg_change = (total_change / total_value * 100) if total_value > 0 else 0
        
        
        sorted_by_change = sorted(
            holdings,
            key=lambda x: x.get("change_24h", 0),
            reverse=True
        )
        
        best = sorted_by_change[0] if sorted_by_change else None
        worst = sorted_by_change[-1] if sorted_by_change else None
        
        
        winners = [h for h in holdings if h.get("change_24h", 0) > 0]
        losers = [h for h in holdings if h.get("change_24h", 0) < 0]
        
        return {
            "total_change_24h": round(avg_change, 2),
            "best_performer": {
                "symbol": best["symbol"],
                "name": best.get("name", best["symbol"]),
                "change": round(best.get("change_24h", 0), 2),
                "value": best["value"],
            } if best else None,
            "worst_performer": {
                "symbol": worst["symbol"],
                "name": worst.get("name", worst["symbol"]),
                "change": round(worst.get("change_24h", 0), 2),
                "value": worst["value"],
            } if worst else None,
            "winners_count": len(winners),
            "losers_count": len(losers),
        }
    
    def _generate_insights(
        self,
        holdings: List[Dict],
        total_value: float
    ) -> List[str]:
        
        insights = []
        
        if not holdings:
            insights.append(
                "Portfolio is empty. Start by acquiring some crypto assets on your chosen chain."
            )
            return insights
        
        
        if len(holdings) < 3:
            insights.append(
                f"Low diversification detected ({len(holdings)} holding). "
                f"Consider diversifying across 3-5 different assets to reduce risk. "
                f"Mix of large-cap and promising smaller projects is recommended."
            )
        
        
        top_holding = holdings[0]
        if top_holding["allocation"] > 60:
            insights.append(
                f"{top_holding['symbol']} represents {top_holding['allocation']:.1f}% of your portfolio. "
                f"High concentration increases risk. Consider trimming to 40-50% and diversifying."
            )
        
        
        losing_holdings = [h for h in holdings if h.get("change_24h", 0) < -10]
        if len(losing_holdings) > len(holdings) * 0.5:
            insights.append(
                f"More than half your holdings are down >10% in 24h. "
                f"Market may be experiencing volatility. Consider dollar-cost averaging if you believe in long-term."
            )
        
        
        gaining_holdings = [h for h in holdings if h.get("change_24h", 0) > 10]
        if len(gaining_holdings) > len(holdings) * 0.5:
            insights.append(
                f"More than half your holdings are up >10% in 24h "
                f"Strong performance. Consider taking some profits or rebalancing to lock in gains."
            )
        
        
        small_holdings = [h for h in holdings if h["allocation"] < 5]
        if len(small_holdings) > 5:
            insights.append(
                f"You have {len(small_holdings)} small holdings (<5% each). "
                f"Total value: ${sum(h['value'] for h in small_holdings):.2f}. "
                f"Consider consolidating into fewer, larger positions to simplify management."
            )
        
        
        if total_value < 100:
            insights.append(
                "Small portfolio detected (<$100). Focus on building core positions "
                "in established assets (ETH on your chain). Avoid over-diversification with small amounts."
            )
        elif total_value > 10000:
            insights.append(
                "Substantial portfolio (>$10,000). You may benefit from advanced strategies: "
                "staking for passive income, liquidity provision in DeFi protocols (Uniswap, Aave), "
                "or exploring yield farming opportunities."
            )
        elif total_value > 1000:
            insights.append(
                "Solid portfolio base ($1,000-$10,000). Consider exploring DeFi opportunities "
                "like staking or providing liquidity for additional yield."
            )
        
        
        unverified = [h for h in holdings if not h.get("verified", False)]
        if len(unverified) > 0:
            unverified_symbols = [h["symbol"] for h in unverified[:3]]
            insights.append(
                f"{len(unverified)} unverified token(s) detected: {', '.join(unverified_symbols)}. "
                f"Exercise caution and verify token authenticity before making further investments."
            )
        
        
        low_security = [
            h for h in holdings 
            if h.get("security_score") is not None and h.get("security_score", 100) < 50
        ]
        if len(low_security) > 0:
            insights.append(
                f"{len(low_security)} token(s) have low security scores. "
                f"Review smart contracts and consider reducing exposure to high-risk assets."
            )
        
        return insights
    
    def generate_recommendations(
        self,
        analysis: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
       
        recommendations = []
        
        holdings = analysis.get("holdings", [])
        risk = analysis.get("risk", {})
        allocation = analysis.get("allocation", {})
        performance = analysis.get("performance", {})
        total_value = analysis["summary"]["total_value"]
        
       
        if len(holdings) < 3:
            recommendations.append({
                "type": "Diversification",
                "priority": "High",
                "action": "Add 2-3 more positions across different sectors",
                "reasoning": (
                    "Low diversification increases risk. Your portfolio is vulnerable "
                    "to single-asset volatility. Consider adding:\n"
                    "Large-cap stable asset (ETH if not main holding)\n"
                    "DeFi blue-chip (AAVE, UNI, LINK)\n"
                    "Layer 2 or infrastructure token (ARB, OP, MATIC)"
                ),
            })
        
        
        if allocation.get("concentration") == "High":
            top_symbol = holdings[0]["symbol"] if holdings else "N/A"
            top_allocation = holdings[0]["allocation"] if holdings else 0
            recommendations.append({
                "type": "Rebalancing",
                "priority": "Medium",
                "action": f"Reduce {top_symbol} from {top_allocation:.1f}% to 40-50%",
                "reasoning": (
                    f"High concentration in {top_symbol} creates risk. "
                    f"Consider taking profits and diversifying into other quality assets. "
                    f"Target allocation: 40-50% in top holding, spread rest across 3-4 assets."
                ),
            })
        
        
        if risk.get("level") == "High":
            recommendations.append({
                "type": "Risk Management",
                "priority": "High",
                "action": "Review and reduce risk exposure",
                "reasoning": (
                    f"Portfolio risk level is high. Issues identified:\n"
                    f"{chr(10).join('• ' + factor for factor in risk.get('factors', []))}\n"
                    f"Consider: reducing position sizes, diversifying, or moving to verified assets."
                ),
            })
        
        
        if performance.get("total_change_24h", 0) > 15:
            recommendations.append({
                "type": "Profit Taking",
                "priority": "Medium",
                "action": "Consider taking profits on winning positions",
                "reasoning": (
                    f"Portfolio is up {performance['total_change_24h']:.2f}% in 24h. "
                    f"Strong performance! Consider:\n"
                    f"Selling 20-30% of winning positions\n"
                    f"Moving profits to stablecoins\n"
                    f"Rebalancing to lock in gains"
                ),
            })
        
        
        if performance.get("total_change_24h", 0) < -15:
            recommendations.append({
                "type": "Buying Opportunity",
                "priority": "Medium",
                "action": "Consider dollar-cost averaging into quality assets",
                "reasoning": (
                    f"Portfolio is down {abs(performance['total_change_24h']):.2f}% in 24h. "
                    f"Market dip could be buying opportunity. Strategy:\n"
                    f"Don't invest all at once\n"
                    f"Use DCA (spread purchases over days/weeks)\n"
                    f"Focus on proven assets with strong fundamentals"
                ),
            })
        
        
        if total_value > 1000:
            recommendations.append({
                "type": "DeFi Strategies",
                "priority": "Low",
                "action": "Explore DeFi for passive income",
                "reasoning": (
                    f"With ${total_value:,.2f} portfolio, you can explore DeFi:\n"
                    f"Staking: Earn 3-8% APY on ETH, MATIC, etc.\n"
                    f"Liquidity provision: 10-30% APY on Uniswap pairs\n"
                    f"Lending: 2-15% APY on Aave/Compound\n"
                    f"Start small (10-20% of portfolio) and learn the risks."
                ),
            })
        
        
        small_holdings = [h for h in holdings if h["allocation"] < 5]
        if len(small_holdings) > 5:
            total_small = sum(h["value"] for h in small_holdings)
            recommendations.append({
                "type": "Portfolio Cleanup",
                "priority": "Low",
                "action": f"Consolidate {len(small_holdings)} small positions",
                "reasoning": (
                    f"You have {len(small_holdings)} holdings under 5% each (${total_small:.2f} total). "
                    f"Benefits of consolidating:\n"
                    f"Easier to manage and track\n"
                    f"Lower gas fees\n"
                    f"More focused strategy\n"
                    f"Consider: selling tiny positions and moving funds to core holdings."
                ),
            })
        
        return recommendations


__all__ = ["PortfolioAnalyzer"]