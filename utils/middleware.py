from django.conf import settings
from django.utils import timezone

from main.models import Profile
from utils.social_pipeline import _fetch_player

from django.http import Http404
from django.urls import reverse
from django.conf import settings

MAX_AGE_HOURS = getattr(settings, "STEAM_PROFILE_MAX_AGE", 12)

# -----------------------------------------------------------------------------
class RefreshSteamProfileMiddleware:
    """
    Refresh Steam profile data when it becomes stale.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            self._maybe_refresh(request.user)
        return self.get_response(request)

    # -----------------------------------------------------------------------------
    def _maybe_refresh(self, user):
        """
        Check profile age and update username/avatar if too old.
        """
        profile: Profile | None = getattr(user, "profile", None)
        if not profile or not profile.steamid:
            return

        # Skip if last sync is recent
        if profile.last_steam_sync:
            age = (timezone.now() - profile.last_steam_sync).total_seconds() / 3600
            if age < MAX_AGE_HOURS:
                return

        # Fetch fresh data
        player = _fetch_player(profile.steamid)
        if not player:
            return

        changed = False
        persona = player.get("personaname")
        avatar  = player.get("avatarfull")

        # Update username if needed
        if persona and user.username != persona:
            user.username = persona[:150]
            user.save(update_fields=["username"])

        # Update avatar if needed
        if avatar and avatar != profile.steam_avatar:
            profile.steam_avatar = avatar
            changed = True

        # Save changes and timestamp
        if changed or not profile.last_steam_sync:
            profile.last_steam_sync = timezone.now()
            profile.save(update_fields=["steam_avatar", "last_steam_sync"])

# -----------------------------------------------------------------------------
class AdminRestrictIPMiddleware:
    """
    Restrict access to the Django admin site to a whitelist of IP addresses.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Precompute the admin URL prefix for efficiency
        self.admin_root = reverse('admin:index')

    def __call__(self, request):
        # Only enforce on paths under the admin root
        if request.path.startswith(self.admin_root):
            client_ip = self.get_client_ip(request)
            # If the client IP is not allowed, pretend the page doesn't exist
            if client_ip not in settings.ADMIN_ALLOWED_IPS:
                raise Http404
        # Proceed with the normal response otherwise
        return self.get_response(request)

    def get_client_ip(self, request):
        """
        Retrieve the real client IP, respecting X-Forwarded-For if behind a proxy.
        """
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            # Take the first IP in the list (the original client)
            return xff.split(',')[0].strip()
        # Fallback to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR')