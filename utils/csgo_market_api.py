from __future__ import annotations
from django.conf import settings

import logging
import threading
import time
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://market.csgo.com/api/v2"
API_KEY  = settings.MARKETCSGO_API_KEY

# -----------------------------------------------------------------------------
class RateLimiter:
    """
    Simple token-bucket rate limiter to throttle API requests.
    """
    def __init__(self, rate: int, per: int) -> None:
        # rate: number of tokens, per: time window in seconds
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
        self.lock = threading.Lock()

    # -----------------------------------------------------------------------------
    def wait(self) -> None:
        """
        Block until a request is allowed under the rate limit.
        """
        with self.lock:
            now = time.time()
            # Refill tokens
            self.allowance += (now - self.last_check) * (self.rate / self.per)
            self.allowance = min(self.allowance, self.rate)
            self.last_check = now

            # If no tokens, sleep until one is available
            if self.allowance < 1:
                sleep_time = (1 - self.allowance) * (self.per / self.rate)
                time.sleep(sleep_time)
                self.allowance = 0
            else:
                self.allowance -= 1


# Single shared limiter: max 5 calls per second
rate_limiter = RateLimiter(rate=5, per=1)

# -----------------------------------------------------------------------------
def _req(method: str, url: str, **kw) -> requests.Response:
    """
    Wrapper around requests.request that applies rate limiting.
    """
    rate_limiter.wait()
    return requests.request(method, url, **kw)

# -----------------------------------------------------------------------------
def get_lowest_price(hash_name: str) -> Tuple[bool, int]:
    """
    Fetch the lowest listing price (in cents) for an item.
    Returns (success, price_cents).
    """
    url = (
        f"{BASE_URL}/search-list?"
        f"key={API_KEY}&hash_name={hash_name}&needed=1"
    )
    try:
        r = _req("GET", url, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data.get("success"):
            logger.warning("search-list error %s", data)
            return False, 0

        lst = data.get("data", {}).get("list", [])
        if not lst:
            logger.info("No listings for %s", hash_name)
            return False, 0

        # The price field is the lowest available
        price_cents = int(lst[0]["price"])
        return True, price_cents

    except Exception as exc:
        logger.error("get_lowest_price(%s) → %s", hash_name, exc)
        return False, 0

# -----------------------------------------------------------------------------
def buy_for_item(
    *,
    hash_name: str,
    price: int,
    partner: str,
    token: str,
    chance_to_transfer: int | None = None,
    custom_id: str | None = None,
) -> Tuple[bool, dict]:
    """
    Send a buy-for request to purchase an item via the API.
    Returns (success, response_data) where response_data includes offer info.
    """
    params: dict[str, str | int] = {
        "key": API_KEY,
        "hash_name": hash_name,
        "price": price,
        "partner": partner,
        "token": token,
    }
    if chance_to_transfer is not None:
        params["chance_to_transfer"] = chance_to_transfer
    if custom_id:
        params["custom_id"] = custom_id

    url = f"{BASE_URL}/buy-for"
    r = _req("GET", url, params=params, timeout=15)

    if r.status_code == 200:
        data = r.json()
        return bool(data.get("success")), data

    # Non-200 responses are treated as failures
    return False, {"error": "HTTP error", "code": r.status_code}

# -----------------------------------------------------------------------------
def get_buy_info_by_custom_id(custom_id: str) -> Tuple[bool, dict]:
    """
    Retrieve the status and details of a prior buy-for request by its custom_id.
    Returns (success, data) where data includes stage and status.
    """
    url = (
        f"{BASE_URL}/get-buy-info-by-custom-id?"
        f"key={API_KEY}&custom_id={custom_id}"
    )
    try:
        r = _req("GET", url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            return True, data.get("data", {})
        return False, data
    except Exception as exc:
        logger.error("get_buy_info_by_custom_id(%s) → %s", custom_id, exc)
        return False, {"error": str(exc)}

# -----------------------------------------------------------------------------
def get_list_buy_info_by_custom_ids(custom_ids: list[str]) -> tuple[bool, dict]:
    """
    Batch-fetch statuses for multiple buy-for requests.
    Returns (success, data) mapping each custom_id to its info.
    """
    url = f"{BASE_URL}/get-list-buy-info-by-custom-id"
    params = [("key", API_KEY)] + [("custom_id[]", cid) for cid in custom_ids]
    r = _req("GET", url, params=params, timeout=10)
    if r.status_code != 200:
        return False, {}

    data = r.json()
    return bool(data.get("success")), data.get("data", {})

