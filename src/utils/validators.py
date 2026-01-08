

from typing import List
import re


class ValidationError(Exception):
    
    pass


def validate_symbol(symbol: str) -> str:
    
    if not symbol or not isinstance(symbol, str):
        raise ValidationError("Symbol must be a non-empty string")

    symbol = symbol.strip().upper()
    
    if len(symbol) < 1 or len(symbol) > 20:
        raise ValidationError(
            f"Symbol '{symbol}' has invalid length. "
            f"Must be 1-20 characters (got {len(symbol)})"
        )
    
    if not re.match(r'^[A-Z0-9\-]+$', symbol):
        raise ValidationError(
            f"Symbol '{symbol}' contains invalid characters. "
            f"Only letters, numbers, and hyphens allowed"
        )
    
    return symbol


def validate_symbols(symbols: List[str]) -> List[str]:
    
    if not isinstance(symbols, list):
        raise ValidationError(
            f"Symbols must be a list, got {type(symbols).__name__}"
        )

    if not symbols:
        raise ValidationError("Symbols list cannot be empty")

    if len(symbols) > 20:
        raise ValidationError(
            f"Too many symbols. Maximum 20 allowed, got {len(symbols)}"
        )

    validated = []
    for i, symbol in enumerate(symbols):
        try:
            validated.append(validate_symbol(symbol))
        except ValidationError as e:
            raise ValidationError(f"Symbol at index {i}: {str(e)}")

    return validated


def validate_limit(limit: int, min_val: int = 1, max_val: int = 500) -> int:
    
    if not isinstance(limit, int):
        try:
            limit = int(limit)
        except (ValueError, TypeError) as e:
            raise ValidationError(
                f"Limit must be an integer, got '{limit}' ({type(limit).__name__})"
            )

    if limit < min_val or limit > max_val:
        raise ValidationError(
            f"Limit must be between {min_val} and {max_val}, got {limit}"
        )

    return limit


def validate_timeframe(timeframe: str) -> str:
    
    allowed_timeframes = ["1h", "24h", "7d", "30d"]

    if not isinstance(timeframe, str):
        raise ValidationError(
            f"Timeframe must be a string, got {type(timeframe).__name__}"
        )

    timeframe = timeframe.strip().lower()

    if timeframe not in allowed_timeframes:
        raise ValidationError(
            f"Invalid timeframe '{timeframe}'. "
            f"Allowed values: {', '.join(allowed_timeframes)}"
        )

    return timeframe


def validate_wallet_address(address: str, chain: str) -> str:
    
    if not address or not isinstance(address, str):
        raise ValidationError("Address must be a non-empty string")
    
    address = address.strip()
    
    
    if chain in ["ethereum", "base", "polygon", "arbitrum", "optimism", "bnb", "avalanche"]:
        
        if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
            raise ValidationError(
                f"Invalid {chain} address format. "
                f"Must be 42 characters starting with 0x"
            )
    
    
    elif chain == "solana":
        
        if len(address) < 32 or len(address) > 44:
            raise ValidationError(
                "Invalid Solana address format. "
                "Must be 32-44 characters"
            )
    
    else:
        raise ValidationError(f"Unsupported chain: {chain}")
    
    return address