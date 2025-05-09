from __future__ import annotations

import logging
import random
import json
import time
from decimal import Decimal

from django.contrib.auth import logout
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from urllib.parse import urlparse, parse_qs

from .models import (
    Case, Item, InventoryItem, Withdrawal,
    CaseOpenStat, TransactionLog
)
from utils.csgo_market_api import (
    get_buy_info_by_custom_id,
    buy_for_item,
    get_lowest_price
)
from utils.utils import steamid32_to_64

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
@require_GET
def load_targets(request):
    """
    Return a list of items for the upgrade panel with pagination.
    Query params: offset=N, limit=M.
    """
    try:
        limit  = max(1, min(int(request.GET.get("limit", 60)), 200))
        offset = max(0,     int(request.GET.get("offset", 0)))
    except ValueError:
        return JsonResponse({"success": False, "message": "bad offset/limit"}, status=400)

    qs = Item.objects.order_by("-price")[offset: offset + limit]
    data = [_item_json(it) for it in qs]

    return JsonResponse(
        {"success": True, "items": data},
        json_dumps_params={"ensure_ascii": False}
    )


# -----------------------------------------------------------------------------
# Helper to serialize Item or InventoryItem to JSON
# -----------------------------------------------------------------------------
def _item_json(obj, *, is_inv: bool = False) -> dict:
    """
    Serialize an Item or InventoryItem to a JSON-friendly dict.
    """
    it = obj.item if is_inv else obj
    rarity = it.rarity or None
    color = rarity.color if rarity else '#ffffff'
    return {
        "id":            obj.id,
        "weapon_name":   it.weapon_name,
        "skin_name":     it.skin_name or "",
        "price":         float(it.price),
        "rarity":        rarity.name if rarity else None,
        "rarity_color":  color,
        "rarity_color_full":  color + "80",
        "rarity_color_light": color + "33",
        "image_url":     it.image.url if it.image else "",
        "drop_chance":   getattr(obj, 'drop_chance', None),
    }


# -----------------------------------------------------------------------------
# CASES: List / Search / Filter
# -----------------------------------------------------------------------------
def cases_list(request):
    """
    Display active cases grouped by section.
    """
    sections = (
        Case.objects.select_related("section")
        .filter(active=True)
        .order_by("section__id")
    )
    return render(request, "main/cases_list.html", {"sections": sections})


@require_GET
def cases_search(request):
    """
    Search active cases by title term and return JSON.
    """
    term = request.GET.get("term", "").lower().strip()
    qs = Case.objects.filter(active=True)
    data = [_case_json(c) for c in qs if term in c.title.lower()]
    return JsonResponse({"main": data, "empty": not data})


@require_GET
def cases_filter_search(request):
    """
    Filter active cases by title term and price range and return JSON.
    """
    term = request.GET.get("term", "").lower().strip()
    try:
        min_price = Decimal(request.GET.get("min_price")) if request.GET.get("min_price") else None
        max_price = Decimal(request.GET.get("max_price")) if request.GET.get("max_price") else None
    except Exception:
        min_price = max_price = None

    qs = Case.objects.filter(active=True)
    data: list[dict] = []
    for c in qs:
        if term and term not in c.title.lower():
            continue
        if min_price and c.price < min_price:
            continue
        if max_price and c.price > max_price:
            continue
        data.append(_case_json(c))
    return JsonResponse({"main": data, "empty": not data})


# -----------------------------------------------------------------------------
# JSON / CASE DETAIL / SPIN
# -----------------------------------------------------------------------------
def _case_json(case: Case) -> dict:
    """
    Convert a Case instance to a JSON-serializable dict.
    """
    return {
        "id": case.id,
        "title": case.title,
        "price": f"{case.price:.2f}",
        "old_price": f"{case.old_price:.2f}" if case.old_price else None,
        "slug": case.slug,
        "item_count": case.item_count,
        "box_image": case.box_image.url if case.box_image else "",
    }


def case_detail(request, slug):
    """
    Display case details and compute how much more the user needs.
    """
    case = get_object_or_404(Case, slug=slug, active=True)
    items_qs = case.case_items.select_related('item__rarity')
    case_items = []
    for ci in items_qs:
        item = ci.item
        rarity = item.rarity
        case_items.append({
            'id': ci.item.id,
            'weapon_name': item.weapon_name,
            'skin_name': item.skin_name or '',
            'image_url': item.image.url,
            'rarity': rarity.name if rarity else None,
            'rarity_color': rarity.color if rarity else '#ffffff',
            'rarity_color_full': (rarity.color + "80") if rarity else "#ffffff80",
            'rarity_color_light': (rarity.color + "33") if rarity else "#ffffff33",
            'drop_chance': ci.drop_chance,
            'price': float(item.price),
        })
    need_amount = None
    if request.user.is_authenticated:
        bal = request.user.profile.balance
        if bal < case.price:
            need_amount = case.price - bal

    return render(request, 'case/case_detail.html', {
        'case':            case,
        'case_items_json': json.dumps(case_items),
        'need_amount':     need_amount,
    })


@require_POST
@login_required
def spin_case(request, slug):
    """
    Process a case spin, award an item, and update user records.
    """
    case = get_object_or_404(Case, slug=slug, active=True)
    profile = request.user.profile

    if profile.balance < case.price:
        return JsonResponse({'error': 'Insufficient funds'}, status=400)
    profile.balance -= case.price
    profile.save(update_fields=['balance'])

    ci_list = list(case.case_items.filter(never_drop=False).select_related('item'))
    items = [ci.item for ci in ci_list]
    weights = [ci.drop_chance for ci in ci_list]

    won_item = random.choices(items, weights=weights, k=1)[0]
    inv_item = InventoryItem.objects.create(profile=profile, item=won_item)

    TransactionLog.objects.create(
        user=request.user,
        action_type='open_case',
        details=(
            f"Opened case «{case.title}» (id={case.id}), "
            f"won «{won_item}» (id={won_item.id}), "
            f"charged {case.price:.2f}"
        )
    )

    stat, _ = CaseOpenStat.objects.get_or_create(user=request.user, case=case)
    stat.opens += 1
    stat.save(update_fields=['opens'])

    if not profile.favorite_case or stat.opens > CaseOpenStat.objects.get(
        user=request.user, case=profile.favorite_case
    ).opens:
        profile.favorite_case = case
    if not profile.best_drop_item or won_item.price > profile.best_drop_item.price:
        profile.best_drop_item = won_item

    profile.cases_opened += 1
    profile.save(update_fields=[
        'favorite_case', 'best_drop_item', 'cases_opened', 'balance'
    ])

    return JsonResponse({
        'winning_item_id':    won_item.id,
        'inventory_item_id':  inv_item.id,
        'item': {
            'weapon_name': won_item.weapon_name,
            'skin_name':   won_item.skin_name or '',
            'price':       float(won_item.price),
            'image_url':   won_item.image.url,
            'rarity_color': won_item.rarity.color if won_item.rarity else '#ffffff',
        },
        'new_balance': float(profile.balance),
    })


# -----------------------------------------------------------------------------
# PROFILE VIEW
# -----------------------------------------------------------------------------
@login_required
def profile_view(request):
    """
    Render the user profile with inventory and withdrawal statuses.
    """
    profile = request.user.profile
    now = timezone.now()

    pending = Withdrawal.objects.filter(user=request.user, status="pending")
    status_dict: dict[int, str] = {}
    for wd in pending:
        ok, info = get_buy_info_by_custom_id(wd.custom_id)
        stage = info.get('stage')
        if ok and stage:
            status_dict[wd.inventory_item.id] = str(stage)

    withdrawn_ids = list(
        Withdrawal.objects
        .filter(user=request.user, status="completed")
        .values_list("inventory_item_id", flat=True)
    )

    inventory_items = (
        InventoryItem.objects
        .filter(profile=profile)
        .exclude(id__in=withdrawn_ids)
        .select_related("item")
    )

    return render(request, "main/profile.html", {
        'profile': profile,
        'inventory_items': inventory_items,
        'status_dict': status_dict,
        'cases_opened': profile.cases_opened,
        'items_withdrawn': len(withdrawn_ids),
        'upgrades_count': profile.upgrades_count,
        'contracts_count': profile.contracts_count,
        'favorite_case': profile.favorite_case,
        'best_drop_item': profile.best_drop_item,
        'active_withdrawals_json': json.dumps(list(pending.values_list("inventory_item_id", flat=True))),
    })


# -----------------------------------------------------------------------------
# POLL WITHDRAWALS
# -----------------------------------------------------------------------------
@login_required
def poll_withdrawals_view(request):
    """
    Check pending withdrawals, update statuses, and return removed/returned item IDs.
    """
    now = timezone.now()
    pending_qs = (
        Withdrawal.objects
        .filter(user=request.user, status="pending")
        .select_related("inventory_item")
    )

    removed, returned = [], []
    for wd in pending_qs:
        ok, info = get_buy_info_by_custom_id(wd.custom_id)
        stage = int(info.get("stage", 0)) if ok else None
        status_failed = (info.get("status") == "failed")
        age = (now - wd.created_at).total_seconds()

        if stage == 2:
            removed.append(wd.inventory_item.id)
            wd.status = "completed"
            wd.save(update_fields=["status"])
            wd.inventory_item.delete()
            continue

        if stage in (4, 5):
            if age < 300 or not status_failed:
                continue

        if status_failed:
            if wd.fail_seen_at is None:
                wd.fail_seen_at = now
                wd.save(update_fields=["fail_seen_at"])
                continue
            if (now - wd.fail_seen_at).total_seconds() < 60:
                continue

        if age < 360:
            continue

        returned.append(wd.inventory_item.id)
        wd.status = "failed"
        wd.save(update_fields=["status"])
        inv = wd.inventory_item
        inv.pending = False
        inv.save(update_fields=["pending"])

    return JsonResponse({"removed": removed, "returned": returned})


# -----------------------------------------------------------------------------
# UPDATE TRADE URL
# -----------------------------------------------------------------------------
@login_required
def update_trade_url_view(request):
    """
    Validate and update the user's trade URL.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid method"}, status=400)

    url_raw = request.POST.get("trade_url", "").strip()
    if not url_raw.startswith("https://steamcommunity.com/tradeoffer/new/?"):
        return JsonResponse({"success": False, "message": "Invalid link"}, status=400)

    qs = parse_qs(urlparse(url_raw).query)
    partner_32 = qs.get("partner", [None])[0]
    token = qs.get("token", [None])[0]
    if not partner_32 or not token:
        return JsonResponse({"success": False, "message": "Invalid link"}, status=400)

    profile = request.user.profile
    if not profile.steamid:
        return JsonResponse({"success": False, "message": "Log in via Steam"}, status=400)

    try:
        partner_64 = steamid32_to_64(int(partner_32))
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid link"}, status=400)

    if str(partner_64) != str(profile.steamid):
        return JsonResponse({"success": False, "message": "Link not yours"}, status=400)

    profile.trade_url = url_raw
    profile.save(update_fields=["trade_url"])
    return JsonResponse({"success": True, "message": "Trade link saved"})


# -----------------------------------------------------------------------------
# SELL ITEMS
# -----------------------------------------------------------------------------
@login_required
@require_POST
def sell_items(request):
    """
    Sell selected inventory items and update the user's balance.
    """
    item_ids = request.POST.getlist("item_ids[]")
    if not item_ids:
        return JsonResponse({"success": False, "error": "No items selected"}, status=400)

    with transaction.atomic():
        qs = InventoryItem.objects.select_for_update() \
            .filter(profile=request.user.profile, id__in=item_ids)
        if not qs.exists():
            return JsonResponse({"success": False, "error": "No matching items"}, status=404)

        total_price = sum(i.item.price for i in qs)
        profile = request.user.profile
        profile.balance += total_price
        profile.save(update_fields=["balance"])

        removed_ids = list(qs.values_list("id", flat=True))
        qs.delete()

    return JsonResponse({
        "success":     True,
        "new_balance": float(profile.balance),
        "removed_ids": removed_ids
    })


# -----------------------------------------------------------------------------
# BUY FOR ITEM (WITHDRAW)
# -----------------------------------------------------------------------------
@login_required
def buy_for_item_view(request):
    """
    Create withdrawal offers for selected items.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    item_ids = request.POST.getlist("item_ids[]")
    if not item_ids:
        return JsonResponse({"error": "No item_ids"}, status=400)

    ok_ids, err_msgs = [], []
    profile = request.user.profile

    if profile.withdraw_blocked:
        return JsonResponse({"error": "Unknown error"}, status=400)

    qs = parse_qs(urlparse(profile.trade_url or "").query)
    partner, token = qs.get("partner", [""])[0], qs.get("token", [""])[0]
    if not partner or not token:
        return JsonResponse({"error": "No trade link set"}, status=400)

    for item_id in item_ids:
        try:
            inv_item = InventoryItem.objects.get(id=item_id, profile=profile)
        except InventoryItem.DoesNotExist:
            err_msgs.append(f"{item_id}: not found")
            continue

        if inv_item.pending or Withdrawal.objects.filter(
            user=request.user, inventory_item=inv_item, status="pending"
        ).exists():
            err_msgs.append(f"{item_id}: already pending")
            continue

        hash_name = inv_item.item.market_hash_name or (
            f"{inv_item.item.weapon_name} | {inv_item.item.skin_name}"
            if inv_item.item.skin_name else inv_item.item.weapon_name
        )

        base_usd = float(inv_item.item.price)
        price_cop = int(round(base_usd * 100 * 1.05))
        logger.debug("Using local price: base_usd=%s → price_cop=%s", base_usd, price_cop)

        custom_id = f"{request.user.id}_{item_id}_{int(time.time())}"

        logger.debug("Calling buy_for_item hash_name=%r price=%s partner=%s token=%s",
                     hash_name, price_cop, partner, token)

        ok, data = buy_for_item(
            hash_name=hash_name,
            price=price_cop,
            partner=partner,
            token=token,
            custom_id=custom_id
        )

        if not ok or not (data.get("success") and (data.get("id") or data.get("data", {}).get("offer_id"))):
            err = data.get("error") or data.get("message") or f"{item_id}: unknown error"
            err_msgs.append(f"{item_id}: {err}")
            continue

        inv_item.pending = True
        inv_item.save(update_fields=["pending"])

        withdrawal = Withdrawal.objects.create(
            user=request.user,
            inventory_item=inv_item,
            custom_id=custom_id,
            offer_id = data.get("id") or data.get("data", {}).get("offer_id"),
            status="pending"
        )
        ok_ids.append(inv_item.id)

    if not ok_ids:
        return JsonResponse({"success": False, "error": "No withdrawals created", "failed": err_msgs}, status=400)

    return JsonResponse({"success": True, "created": ok_ids, "failed": err_msgs})

# -----------------------------------------------------------------------------
# UPGRADE VIEW
# -----------------------------------------------------------------------------
def upgrades_view(request):
    """
    Render upgrade page with user items and available targets.
    """
    if request.user.is_authenticated:
        profile = request.user.profile
        left_items = [
            _item_json(inv, is_inv=True)
            for inv in InventoryItem.objects.filter(profile=profile)
        ]
        right_items = [
            _item_json(it)
            for it in Item.objects.all().order_by("-price")[:1000]
        ]
    else:
        profile     = None
        left_items  = []
        right_items = []

    return render(request, "main/upgrades.html", {
        "profile":          profile,
        "left_items_json":  json.dumps(left_items),
        "right_items_json": json.dumps(right_items),
    })


@login_required
def create_upgrade_view(request):
    """
    Handle upgrade creation and determine success or partial refund.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)
    data = json.loads(request.body or "{}")
    user_item_ids = data.get("user_item_ids", [])
    target_item_id = data.get("target_item_id")
    extra_balance = Decimal(str(data.get("extra_balance", 0)))

    profile = request.user.profile
    if profile.balance < extra_balance:
        return JsonResponse({"success": False, "message": "Insufficient funds"}, status=400)

    profile.balance -= extra_balance
    profile.save(update_fields=["balance"])

    used_qs = InventoryItem.objects.filter(profile=profile, id__in=user_item_ids)
    total_price = sum(inv.item.price for inv in used_qs)
    used_qs.delete()

    target_item = get_object_or_404(Item, id=target_item_id)
    attempt_value = total_price + extra_balance
    chance = min((attempt_value / target_item.price) * 100, 75)
    is_win = random.uniform(0, 100) <= float(chance)

    result = None
    if is_win:
        new_inv = InventoryItem.objects.create(profile=profile, item=target_item)
        profile.upgrades_count += 1
        profile.save(update_fields=["upgrades_count"])
        result = _item_json(new_inv, is_inv=True)
    else:
        cashback = attempt_value * Decimal("0.02")
        profile.balance += cashback
        profile.save(update_fields=["balance"])

    TransactionLog.objects.create(
        user=request.user,
        action_type='upgrade',
        details=(
            f"{'Success' if is_win else 'Fail'} upgrade to «{target_item}» "
            f"(id={target_item.id}), bet {attempt_value:.2f}, chance {chance:.2f}%"
        )
    )

    return JsonResponse({
        "success": True,
        "is_win": is_win,
        "chance_percent": float(chance),
        "new_balance": float(profile.balance),
        "result_item": result,
    })


# -----------------------------------------------------------------------------
# CONTRACTS VIEW
# -----------------------------------------------------------------------------
def contracts_view(request):
    """
    Render contract page with user items.
    """
    if request.user.is_authenticated:
        profile = request.user.profile
        left_items = [
            _item_json(inv, is_inv=True)
            for inv in InventoryItem.objects.filter(profile=profile)
        ]
    else:
        profile = None
        left_items = []

    return render(
        request,
        "main/contracts.html",
        {
            "profile": profile,
            "left_items_json": json.dumps(left_items),
        },
    )


@login_required
def create_contract_view(request):
    """
    Handle contract creation and determine the outcome.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)

    data          = json.loads(request.body or "{}")
    user_item_ids = data.get("user_item_ids", [])
    extra_balance = Decimal(str(data.get("extra_balance", 0)))

    if len(user_item_ids) < 3:
        return JsonResponse({"success": False, "message": "At least 3 items required"}, status=400)

    profile = request.user.profile
    if profile.balance < extra_balance:
        return JsonResponse({"success": False, "message": "Insufficient funds"}, status=400)

    profile.balance -= extra_balance
    profile.save(update_fields=["balance"])

    used_qs      = InventoryItem.objects.filter(profile=profile, id__in=user_item_ids)
    total_value  = sum(inv.item.price for inv in used_qs)
    used_qs.delete()

    attempt = total_value + extra_balance
    roll    = random.uniform(0, 100)
    if roll <= 50:
        mult = 0.5
    elif roll <= 94:
        mult = 2
    elif roll <= 98:
        mult = 3
    elif roll <= 98.9:
        mult = 4
    else:
        mult = 5

    result_value = attempt * Decimal(str(mult))
    low, high    = attempt * Decimal("0.5"), result_value
    pool         = [i for i in Item.objects.all() if low <= i.price <= high] or \
                   [min(Item.objects.all(), key=lambda x: abs(x.price - high))]
    chosen       = random.choice(pool)
    new_inv      = InventoryItem.objects.create(profile=profile, item=chosen)

    profile.contracts_count += 1
    profile.save(update_fields=["contracts_count"])

    TransactionLog.objects.create(
        user=request.user,
        action_type="contract",
        details=(
            f"Contract of {len(user_item_ids)} items (sum {total_value:.2f} + extra {extra_balance:.2f}), "
            f"mult {mult}, result «{chosen}» (id={chosen.id})"
        ),
    )

    return JsonResponse(
        {
            "success": True,
            "multiplier": mult,
            "contract_result_value": float(result_value),
            "new_balance": float(profile.balance),
            "result_item": _item_json(new_inv, is_inv=True),
        }
    )


# -----------------------------------------------------------------------------
# TEST DEPOSIT
# -----------------------------------------------------------------------------
@login_required
def deposit_view(request):
    """
    This function adds 100 units to the user's balance.
    """
    profile = request.user.profile
    profile.balance += Decimal("100.00")
    profile.save(update_fields=["balance"])
    return redirect("main:cases_list")


# -----------------------------------------------------------------------------
# LOGOUT
# -----------------------------------------------------------------------------
@login_required
def logout_view(request):
    """
    Log out the user and redirect to the cases list.
    """
    logout(request)
    return redirect("main:cases_list")
