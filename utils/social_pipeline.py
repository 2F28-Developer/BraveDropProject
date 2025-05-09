import re
import json
import requests
from bs4 import BeautifulSoup

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from main.models import Profile

# Steam Web API endpoint and cache configuration
API_URL = (
    "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    "?key={key}&steamids={steamid}"
)
CACHE_TTL = 60 * 60 * 12  # 12 hours
HEADERS = {
    # Desktop User-Agent to receive full profile layout
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Safari/537.36"
    )
}

def fetch_steam_avatar_from_profile_page(steamid64: str) -> str | None:
    """
    Extract animated GIF or static avatar URL from public profile page.
    """
    url = f"https://steamcommunity.com/profiles/{steamid64}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    html = resp.text

    # 1) Check JS object for animated avatar
    match = re.search(r'var\s+g_rgProfileData\s*=\s*(\{.*?\});', html, re.S)
    if match:
        try:
            data = json.loads(match.group(1))
            gif = data.get("avatarFullAnimated")
            if gif and gif.lower().endswith(".gif"):
                return gif
        except json.JSONDecodeError:
            pass

    soup = BeautifulSoup(html, "html.parser")

    # 2) Select images within avatar container
    avatar_block = soup.select_one("div.playerAvatarAutoSizeInner")
    if avatar_block:
        # Only direct <img> children, skip nested frame
        imgs = [img for img in avatar_block.find_all("img", recursive=False)]
        # If second image exists, it's usually the animated GIF
        if len(imgs) >= 2:
            url = imgs[1].get("src") or imgs[1].get("data-src")
            if url:
                return url
        # Fallback to first image
        if imgs:
            url = imgs[0].get("src") or imgs[0].get("data-src")
            if url:
                return url

    # 3) Final fallback: og:image meta tag
    meta = soup.find("meta", {"property": "og:image"})
    if meta:
        return meta.get("content")

    return None


def _fetch_player(steamid64: str) -> dict | None:
    """
    Retrieve player data from cache or Steam API, then update avatar URL if needed.
    """
    cache_key = f"steam_profile_{steamid64}"
    player = cache.get(cache_key)
    if player:
        return player

    # Fetch from official Steam API
    try:
        resp = requests.get(
            API_URL.format(key=settings.SOCIAL_AUTH_STEAM_API_KEY, steamid=steamid64),
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json().get("response", {}).get("players", [])
        player = data[0] if data else {}
    except Exception:
        player = {}

    # If API returned a GIF, cache and return
    avatar_url = player.get("avatarfull", "")
    if avatar_url.lower().endswith(".gif"):
        cache.set(cache_key, player, CACHE_TTL)
        return player

    # Otherwise, parse the public page for the correct avatar URL
    fallback = fetch_steam_avatar_from_profile_page(steamid64)
    if fallback:
        player["avatarfull"] = fallback

    cache.set(cache_key, player, CACHE_TTL)
    return player


def update_profile_from_steam(strategy, backend, user=None, **kwargs):
    """
    Pipeline hook: update or create Profile after Steam login.
    """
    if backend.name != "steam" or user is None:
        return

    # Extract SteamID64
    steamid64 = None
    response = kwargs.get("response")
    if response and hasattr(response, "identity"):
        steamid64 = response.identity.rstrip("/").split("/")[-1]
    if not steamid64:
        steam_identity = strategy.request.GET.get("openid.identity")
        if steam_identity:
            steamid64 = steam_identity.rstrip("/").split("/")[-1]
    if not steamid64:
        return

    profile, _ = Profile.objects.get_or_create(user=user)
    player = _fetch_player(steamid64)

    persona = player.get("personaname") if player else None
    avatar = player.get("avatarfull") if player else None
    changed = False

    # Update username if changed
    if persona and user.username != persona:
        user.username = persona[:150]
        user.save(update_fields=["username"])

    # Update avatar if changed
    if avatar and avatar != profile.steam_avatar:
        profile.steam_avatar = avatar
        changed = True

    # Update SteamID if changed
    if profile.steamid != steamid64:
        profile.steamid = steamid64
        changed = True

    if changed:
        profile.last_steam_sync = timezone.now()
        profile.save(update_fields=["steam_avatar", "steamid", "last_steam_sync"])
