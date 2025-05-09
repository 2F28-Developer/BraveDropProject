from urllib.parse import urlparse, parse_qs
import math
from decimal import Decimal

BASE_64 = 76561197960265728  # Steam ID offset for conversion

# -----------------------------------------------------------------------------
def steamid32_to_64(id32: int) -> str:
    """Convert a 32-bit Steam ID to its 64-bit representation."""
    return str(id32 + BASE_64)

# -----------------------------------------------------------------------------
def steamid64_to_32(id64: str) -> str | None:
    """Convert a 64-bit Steam ID to its 32-bit representation, or return None if invalid."""
    try:
        return str(int(id64) - BASE_64)
    except ValueError:
        return None

# -----------------------------------------------------------------------------
def is_valid_trade_url(url: str) -> bool:
    """Check whether a given URL is a valid Steam trade offer link."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    if parsed.netloc.lower() != "steamcommunity.com":
        return False
    if parsed.path != "/tradeoffer/new/":
        return False

    qs = parse_qs(parsed.query)
    return bool(qs.get("partner") and qs.get("token"))

# -----------------------------------------------------------------------------
def compute_drop_chance(case_price: Decimal, item_price: Decimal) -> float:
    """
    Compute the drop chance for an item based on case and item prices.
    Uses an exponential decay model.
    """
    ratio = float(item_price / case_price)
    steepness = 0.94
    if ratio <= 1:
        return 1.0
    chance = math.exp(-steepness * (ratio - 1))
    return max(chance, 1e-16)
