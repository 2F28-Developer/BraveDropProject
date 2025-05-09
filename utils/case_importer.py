"""
This module adds items from wiki.cs.money cases into our Django application.
"""

import os
import re
import requests
from decimal import Decimal
from lxml import html
from urllib.parse import urlparse
from requests.exceptions import SSLError, RequestException
from django.core.files.base import ContentFile

from main.models import Item, CaseItem, Case, Rarity
from utils.utils import compute_drop_chance

USER_AGENT = "Mozilla/5.0 (importer)"

class CaseImporterError(Exception):
    """Raised when the importer cannot find or parse any items."""
    pass

RARITY_ORDER = {
    "knife":       0,
    "glove":       0,
    "Covert":      1,
    "Classified":  2,
    "Restricted":  3,
    "Mil-Spec":    4,
}


def parse_card(a, special_kind=None) -> dict:
    """
    Extract item data from a case card element.
    """
    weapon_name = a.xpath('.//div[contains(@class,"szvsuisjrrqalciyqqzoxoaubw")]/text()')[0].strip()
    skin_node   = a.xpath('.//div[contains(@class,"zhqwubnajobxbgkzlnptmjmgwn")]/text()')
    skin_name   = skin_node[0].strip() if skin_node else ""

    # Determine rarity, ignoring StatTrak prefix
    if special_kind == "glove":
        rarity = "Extraordinary"
    else:
        titles = a.xpath('.//div[contains(@class,"nwdmbwsohrhpxvdldicoixwfed")]/@title')
        raw = next((t for t in titles if "StatTrak" not in t), titles[0] if titles else "")
        rarity = raw.lstrip("★ ").strip()

    # Get image URL
    img_srcs   = a.xpath('.//img[starts-with(@src,"http")]/@src') \
              or a.xpath('.//noscript//img/@src')
    image_url  = img_srcs[0].strip() if img_srcs else None

    # Extract numeric prices, stripping all non-digit/dot/minus characters
    price_texts = a.xpath('.//div[contains(@class,"ribvzntfjepldppjrgkwabviqq")]/text()')
    nums = []
    for txt in price_texts:
        tmp = txt.replace("–", "-")
        cleaned = re.sub(r"[^\d\.\-]", "", tmp)
        for part in cleaned.split("-"):
            if re.fullmatch(r"\d+(\.\d+)?", part):
                nums.append(Decimal(part))
    if not nums:
        raise ValueError("No prices found")
    price = min(nums)

    # Build a market_hash_name from the URL path if possible
    href = a.get("href", "")
    parts = [p for p in urlparse(href).path.split("/") if p and p != "ru"]
    if len(parts) >= 3 and parts[0] == "weapons":
        market_hash_name = f"{weapon_name} | {skin_name} (Battle-Scarred)"

    else:
        market_hash_name = ""

    return {
        "weapon_name":      weapon_name,
        "skin_name":        skin_name,
        "rarity":           rarity,
        "image_url":        image_url,
        "price":            price,
        "kind":             special_kind or "normal",
        "market_hash_name": market_hash_name,
    }


def fetch_case_items_from_cs_money(url: str) -> list[dict]:
    """
    Request the case page and parse all normal items.
    """
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    tree = html.fromstring(resp.content)
    cards = tree.xpath('//a[contains(@class,"blzuifkxmlnzwzwpwjzrrtwcse")]')
    if not cards:
        raise CaseImporterError(f"No cards found on {url}")

    items = []
    for a in cards:
        try:
            items.append(parse_card(a))
        except Exception:
            continue
    if not items:
        raise CaseImporterError(f"Failed to parse any cards on {url}")
    return items


def fetch_special_items(case_url: str, kind: str) -> list[dict]:
    """
    Fetch and parse special items (knives, gloves) from subpages.
    De-duplicate by weapon name, keeping the cheapest.
    """
    url = case_url.rstrip("/") + f"/{kind}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    tree = html.fromstring(resp.content)
    anchors = tree.xpath(
        '//div[contains(@class,"gasovxczmdwrpzliptyovkjrjp")]'
        '//a[contains(@class,"blzuifkxmlnzwzwpwjzrrtwcse")]'
    )
    items = []
    for a in anchors:
        try:
            items.append(parse_card(a, special_kind=kind[:-1]))
        except Exception:
            continue

    unique = {}
    for itm in items:
        name = itm["weapon_name"]
        if name not in unique or itm["price"] < unique[name]["price"]:
            unique[name] = itm
    return list(unique.values())


def import_case_from_url(case: Case, url: str) -> tuple[int, list[str]]:
    """
    Main entry: import all items for a given Case model from a wiki.cs.money URL.
    Returns a tuple of (imported_count, list_of_error_messages).
    """
    errors = []

    try:
        items = fetch_case_items_from_cs_money(url)
    except CaseImporterError as e:
        return 0, [str(e)]

    # Include knives and gloves
    items += fetch_special_items(url, "knives")
    items += fetch_special_items(url, "gloves")

    # Sort items by rarity order
    def sort_key(it):
        if it["kind"] in ("knives", "knife"):
            return RARITY_ORDER["knife"]
        if it["kind"] in ("gloves", "glove"):
            return RARITY_ORDER["glove"]
        return RARITY_ORDER.get(it["rarity"], max(RARITY_ORDER.values()) + 1)
    items.sort(key=sort_key)

    count = 0
    for data in items:
        try:
            # Create or update Item record
            item, created = Item.objects.get_or_create(
                weapon_name=data["weapon_name"],
                skin_name=data["skin_name"] or None,
                defaults={
                    "price":            data["price"],
                    "market_hash_name": data["market_hash_name"] or None,
                },
            )
            changed = False
            if item.price != data["price"]:
                item.price = data["price"]
                changed = True
            if not item.market_hash_name and data["market_hash_name"]:
                item.market_hash_name = data["market_hash_name"]
                changed = True
            if changed:
                item.save(update_fields=["price", "market_hash_name"])

            # Ensure Rarity exists and assign it
            rar = Rarity.objects.filter(name__iexact=data["rarity"]).first()
            if not rar:
                rar = Rarity.objects.create(name=data["rarity"], color="#ffffff")
            if item.rarity_id != rar.id:
                item.rarity = rar
                item.save(update_fields=["rarity"])

            # Download and save the image
            try:
                img_resp = requests.get(
                    data["image_url"],
                    headers={"User-Agent": USER_AGENT},
                    timeout=10,
                )
                img_resp.raise_for_status()
                filename = os.path.basename(data["image_url"].split("?", 1)[0])
                item.image.save(filename, ContentFile(img_resp.content), save=False)
                item.save(update_fields=["image"])
            except (SSLError, RequestException):
                pass

            # Link item to the Case and compute drop chance
            ci, _ = CaseItem.objects.update_or_create(
                case=case,
                item=item,
                defaults={"never_drop": False},
            )
            chance = compute_drop_chance(case.price, data["price"])
            ci.drop_chance = chance
            ci.save(update_fields=["drop_chance"])

            count += 1

        except Exception as e:
            errors.append(f"{data['weapon_name']}: {e}")

    return count, errors
