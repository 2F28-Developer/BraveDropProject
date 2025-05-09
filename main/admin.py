from django.contrib.auth.models import User
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _

from .models import (
    TransactionLog, Rarity, Item, CaseSection,
    Case, CaseItem, Profile, Withdrawal
)
from main.models import InventoryItem
from utils.case_importer import import_case_from_url, CaseImporterError
from utils.utils import compute_drop_chance

# -----------------------------------------------------------------------------
@admin.register(Rarity)
class RarityAdmin(admin.ModelAdmin):
    """Admin for Rarity: display name and color."""
    list_display = ('name', 'color')


# -----------------------------------------------------------------------------
class ProfileInline(admin.StackedInline):
    """Inline profile fields in the User admin."""
    model = Profile
    can_delete = False
    fields = ('balance', 'trade_url')


# -----------------------------------------------------------------------------
class InventoryItemInline(admin.TabularInline):
    """Inline display of a user's inventory items."""
    model = InventoryItem
    fk_name = 'profile'
    extra = 0


# -----------------------------------------------------------------------------
# Re-register User to include Profile inline
admin.site.unregister(User)
admin.site.register(User, admin.ModelAdmin)
UserAdmin = admin.site._registry[User]
UserAdmin.inlines = [ProfileInline, InventoryItemInline]


# -----------------------------------------------------------------------------
class CaseItemInline(admin.TabularInline):
    """Inline for items in a Case, showing price and drop chance."""
    model = CaseItem
    extra = 1
    fields = ('item', 'item_price', 'drop_chance', 'never_drop')
    readonly_fields = ('item_price',)

    def item_price(self, obj):
        return obj.item.price
    item_price.short_description = _('Item price')


# -----------------------------------------------------------------------------
@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    """Admin for Case: list display, inlines, and custom actions."""
    list_display = (
        'title', 'price', 'old_price',
        'item_count', 'active', 'section', 'slug'
    )
    inlines = [CaseItemInline]
    change_form_template = 'admin/main/case/change_form.html'

    def get_urls(self):
        """Add URLs for recalculating chances and importing items."""
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/set_chances/',
                self.admin_site.admin_view(self.set_chances_view),
                name='main_case_set_chances',
            ),
            path(
                '<path:object_id>/import_items/',
                self.admin_site.admin_view(self.import_items_view),
                name='main_case_import_items',
            ),
        ]
        return custom + urls

    def set_chances_view(self, request, object_id):
        """Recompute drop chances for all items in the case."""
        case = get_object_or_404(Case, pk=object_id)
        for ci in case.case_items.select_related('item'):
            ci.drop_chance = compute_drop_chance(case.price, ci.item.price)
            ci.save(update_fields=['drop_chance'])
        messages.success(
            request,
            _("Drop chances recalculated successfully")
        )
        return redirect(request.META.get('HTTP_REFERER'))

    def import_items_view(self, request, object_id):
        """Import items into the case from an external URL."""
        case = get_object_or_404(Case, pk=object_id)

        if request.method == 'POST':
            url = request.POST.get('source_url', '').strip()
            try:
                count, errors = import_case_from_url(case, url)
                messages.success(
                    request,
                    _("Imported %(count)d items") % {'count': count}
                )
                for err in errors:
                    messages.warning(request, err)
            except CaseImporterError as e:
                messages.error(
                    request,
                    _("Import error: %(error)s") % {'error': e}
                )
            return redirect(request.META.get('HTTP_REFERER'))

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'original': case,
        }
        return TemplateResponse(
            request,
            'admin/main/case/import_items.html',
            context
        )


# -----------------------------------------------------------------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin for Profile: display and edit balance, trade URL and withdrawal lock."""
    list_display = (
        'user',
        'balance',
        'trade_url',
        'withdraw_blocked',
    )
    list_display_links = ('user',)
    list_editable = (
        'balance',
        'trade_url',
        'withdraw_blocked',
    )
    list_filter = (
        'withdraw_blocked',
    )
    inlines = [InventoryItemInline]


# -----------------------------------------------------------------------------
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Admin for Item: editable price and rarity, filter by rarity."""
    list_display = ('weapon_name', 'skin_name', 'price', 'rarity', 'image')
    list_editable = ('price', 'rarity')
    list_filter = ('rarity',)


# -----------------------------------------------------------------------------
@admin.register(CaseSection)
class CaseSectionAdmin(admin.ModelAdmin):
    """Admin for CaseSection: display section name."""
    list_display = ('name',)


# -----------------------------------------------------------------------------
@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    """Admin for Withdrawal: display status and identifiers."""
    list_display = (
        "id", "inventory_item", "status",
        "custom_id", "offer_id", "created_at"
    )


# -----------------------------------------------------------------------------
@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    """Admin for TransactionLog: display action type and timestamp."""
    list_display = ('action_type', 'timestamp')
