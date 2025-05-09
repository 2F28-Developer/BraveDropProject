import requests
from main.models import Item, Withdrawal
from urllib.parse import parse_qs, urlparse
from utils.csgo_market_api import buy_for_item, get_lowest_price, get_list_buy_info_by_custom_ids

# -----------------------------------------------------------------------------
def update_item_prices():
    """
    Fetch price list from the market API and update Item.price and market_hash_name.
    """
    url = 'https://market.csgo.com/api/v2/prices/USD.json'
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        items_list = data.get('items', [])
        prices_dict = {item["market_hash_name"]: item for item in items_list}
    except Exception:
        return

    db_items = Item.objects.exclude(market_hash_name__isnull=True)
    count = 0
    for item in db_items:
        orig = item.market_hash_name
        pricing = prices_dict.get(orig)
        if not pricing and " | " in orig:
            # fallback to base name if full hash not found
            fallback = orig.split(" | ")[0]
            pricing = prices_dict.get(fallback)
            if pricing:
                item.market_hash_name = fallback
        if pricing:
            new_price = pricing.get("price")
            if new_price is not None:
                item.price = new_price
                item.save(update_fields=['price', 'market_hash_name'])
                count += 1
    return count

# -----------------------------------------------------------------------------
def process_withdrawal(withdrawal_id: int):
    """
    Attempt to create a new withdrawal offer for a single Withdrawal record.
    """
    wd = Withdrawal.objects.select_related("inventory_item", "user__profile").get(id=withdrawal_id)
    inv_item = wd.inventory_item
    profile  = wd.user.profile

    qs = parse_qs(urlparse(profile.trade_url or "").query)
    partner, token = qs.get("partner", [None])[0], qs.get("token", [None])[0]
    if not partner or not token:
        # mark failed and release the item
        wd.status = "failed"
        wd.save(update_fields=["status"])
        inv_item.pending = False
        inv_item.save(update_fields=["pending"])
        return

    hash_name = inv_item.item.market_hash_name or inv_item.item.weapon_name
    ok_price, price_cop = get_lowest_price(hash_name)
    if not ok_price:
        # fallback: price * 1.1
        price_cop = int(round(float(inv_item.item.price) * 100 * 1.1))
    price_cop += 1

    ok, data = buy_for_item(
        hash_name=hash_name,
        price=price_cop,
        partner=partner,
        token=token,
        custom_id=wd.custom_id,
    )

    if ok and data.get("id"):
        wd.offer_id = data["id"]
        wd.status   = "pending"
    else:
        wd.status = "failed"
        inv_item.pending = False
        inv_item.save(update_fields=["pending"])
    wd.save(update_fields=["offer_id", "status"])

# -----------------------------------------------------------------------------
def poll_withdrawals():
    """
    Batch-poll pending withdrawals and update statuses or delete items.
    """
    pending = Withdrawal.objects.filter(status="pending")
    custom_ids = [wd.custom_id for wd in pending]
    if not custom_ids:
        return

    ok, all_info = get_list_buy_info_by_custom_ids(custom_ids)
    removed, returned = [], []

    for wd in pending:
        info = all_info.get(wd.custom_id, {}) or {}
        stage = int(info.get("stage", 0))
        if stage >= 2:
            # offer completed: delete the inventory item
            wd.inventory_item.delete()
            wd.status = "completed"
            removed.append(wd.inventory_item_id)
        elif stage == 5:
            # transfer failed: release the item back
            inv = wd.inventory_item
            inv.pending = False
            inv.save(update_fields=["pending"])
            wd.status = "failed"
            returned.append(inv.id)
        wd.save(update_fields=["status"])
