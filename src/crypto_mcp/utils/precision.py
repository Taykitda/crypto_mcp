"""Financial precision and representation utilities.

Ensures no scientific notation leakage for micro-priced tokens (e.g. PEPE, SHIB)
and provides accurate fixed-point Decimal calculations.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

NumberLike = Union[Decimal, float, int, str]


def to_decimal(val: NumberLike) -> Decimal:
    """Safely convert a number-like value to Decimal."""
    if isinstance(val, Decimal):
        return val
    if isinstance(val, float):
        # Convert via str to avoid float binary approximation issues
        return Decimal(str(val))
    return Decimal(str(val))


def format_crypto_price(val: NumberLike) -> str:
    """Format a price to standard non-scientific notation string.
    
    Examples:
        68450.25 -> "68450.25"
        0.0000084321 -> "0.0000084321" (never "8.4321e-06")
        0.0 -> "0.0"
    """
    d = to_decimal(val)
    if d == 0:
        return "0.0"
    
    # Format with standard string representation without scientific notation
    # In Python, Decimal's format {:f} avoids scientific notation
    formatted = f"{d:f}"
    
    # Trim trailing zeros if there is a decimal point, but keep at least 1 digit or standard cents
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
        if "." not in formatted:
            formatted = f"{formatted}.0"
    return formatted


def display_price_with_currency(
    val: NumberLike, 
    currency: str = "USD"
) -> str:
    """Human and Agent friendly display price.
    
    Examples:
        68450.25, "USD" -> "$68,450.25"
        0.0000084321, "USD" -> "$0.0000084321 (8.432e-6)"
    """
    d = to_decimal(val)
    price_str = format_crypto_price(d)
    
    symbol_map = {
        "usd": "$",
        "eur": "€",
        "cny": "¥",
        "jpy": "¥",
        "gbp": "£",
    }
    cur_sym = symbol_map.get(currency.lower(), f"{currency.upper()} ")
    
    if d >= 1:
        # Format with commas for large numbers
        float_val = float(d)
        if d >= 1000:
            return f"{cur_sym}{float_val:,.2f}"
        return f"{cur_sym}{price_str}"
    
    if d > 0 and d < Decimal("0.001"):
        # For micro tokens, give both exact string and compact exp for Agent clarity
        return f"{cur_sym}{price_str} ({float(d):.3e})"
    
    return f"{cur_sym}{price_str}"


def calculate_conversion(
    amount: NumberLike,
    from_price_usd: NumberLike,
    to_price_usd: NumberLike,
) -> tuple[Decimal, str]:
    """Calculate conversion between two assets based on their USD prices.
    
    Returns:
        (result_decimal, result_string)
    """
    amt = to_decimal(amount)
    from_p = to_decimal(from_price_usd)
    to_p = to_decimal(to_price_usd)
    
    if to_p == 0:
        raise ValueError("Target asset price cannot be zero")
    
    # from_amount * from_price_usd / to_price_usd
    total_usd = amt * from_p
    converted = total_usd / to_p
    
    # Round to reasonable precision (up to 12 decimal places for crypto)
    # to avoid infinite repeating decimals
    converted_rounded = converted.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)
    # Remove trailing zeroes
    conv_str = format_crypto_price(converted_rounded)
    return converted_rounded, conv_str
