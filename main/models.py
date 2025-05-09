from django.contrib.auth.models import User
from django.conf import settings
from django.db import models
from decimal import Decimal

# -----------------------------------------------------------------------------
class TransactionLog(models.Model):
    """
    Logs user actions with type, details, and timestamp.
    """
    ACTION_CHOICES = [
        ('open_case', 'Open Case'),
        ('upgrade', 'Upgrade'),
        ('contract', 'Contract'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action_type} at {self.timestamp}"


# -----------------------------------------------------------------------------
class Rarity(models.Model):
    """
    Defines item rarity with a name and display color.
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Rarity Name"
    )
    color = models.CharField(
        max_length=7,
        default='#ffffff',
        help_text="HEX color, e.g. #FF9800"
    )

    def __str__(self):
        return self.name


# -----------------------------------------------------------------------------
class Item(models.Model):
    """
    Represents a market item with name, image, price, and rarity.
    """
    weapon_name = models.CharField(
        max_length=100,
        verbose_name="Weapon Name"
    )
    skin_name = models.CharField(
        max_length=100,
        verbose_name="Skin Name",
        blank=True,
        null=True
    )
    market_hash_name = models.CharField(
        max_length=255,
        verbose_name="Market Hash Name",
        blank=True,
        null=True,
        help_text="Unique item name for API"
    )
    image = models.ImageField(upload_to='items/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rarity = models.ForeignKey(
        Rarity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        verbose_name="Rarity"
    )

    def __str__(self):
        if self.skin_name:
            return f"{self.weapon_name} | {self.skin_name}"
        return self.weapon_name


# -----------------------------------------------------------------------------
class CaseSection(models.Model):
    """
    Groups cases into named sections.
    """
    name = models.CharField(max_length=100, verbose_name="Section Name")

    def __str__(self):
        return self.name


# -----------------------------------------------------------------------------
class Case(models.Model):
    """
    Defines a case with title, pricing, and section.
    """
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    old_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Old (strikethrough) price if discounted"
    )
    active = models.BooleanField(default=True)
    box_image = models.ImageField(upload_to='main/', blank=True, null=True)
    section = models.ForeignKey(
        CaseSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='main'
    )

    @property
    def item_count(self):
        """
        Returns the number of items in this case.
        """
        return self.case_items.count()

    def __str__(self):
        return self.title


# -----------------------------------------------------------------------------
class CaseItem(models.Model):
    """
    Associates items with a case, including drop chances.
    """
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='case_items'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='item_in_cases'
    )
    drop_chance = models.FloatField(default=1.0)
    never_drop = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.case.title} -> {self.item}"


# -----------------------------------------------------------------------------
class Profile(models.Model):
    """
    Extends User with balance, stats, and Steam integration fields.
    """
    last_steam_sync = models.DateTimeField(null=True, blank=True)
    favorite_case = models.ForeignKey(
        Case,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    best_drop_item = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Balance (USD)"
    )
    trade_url = models.URLField(blank=True, null=True)
    steam_avatar = models.URLField(
        blank=True,
        null=True,
        help_text="Steam avatar URL"
    )
    steamid = models.CharField(max_length=50, blank=True, null=True)

    cases_opened = models.PositiveIntegerField(default=0)
    upgrades_count = models.PositiveIntegerField(default=0)
    withdrawals_count = models.PositiveIntegerField(default=0)
    contracts_count = models.PositiveIntegerField(default=0)

    withdraw_blocked = models.BooleanField(
        default=False,
        verbose_name="Withdrawal block",
        help_text="If enabled, the user will not be able to create withdrawal requests."
    )

    def __str__(self):
        return f"Profile {self.user.username}"


# -----------------------------------------------------------------------------
class CaseOpenStat(models.Model):
    """
    Tracks how many times a user has opened each case.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    opens = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("user", "case")

    def __str__(self):
        return f"{self.user.username} – {self.case.title}: {self.opens}"


# -----------------------------------------------------------------------------
class Withdrawal(models.Model):
    """
    Represents a withdrawal request and its external status.
    """
    fail_seen_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    inventory_item = models.ForeignKey(
        'main.InventoryItem',
        on_delete=models.CASCADE,
        related_name="withdrawals_cases"
    )
    custom_id = models.CharField(max_length=64, unique=True)
    offer_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16,
        choices=(
            ("pending", "pending"),
            ("completed", "completed"),
            ("failed", "failed"),
        ),
        default="pending",
    )
    first_try_failed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.custom_id} ({self.status})"


# -----------------------------------------------------------------------------
class Contract(models.Model):
    """
    Records a contract with items, values, and the resulting item.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    total_items_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Total Items Value (USD)"
    )
    used_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Used Balance (USD)"
    )
    result_item = models.OneToOneField(
        'main.InventoryItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_result"
    )

    def __str__(self):
        return f"Contract #{self.id} by {self.user.username}"


# -----------------------------------------------------------------------------
class InventoryItem(models.Model):
    """
    Represents an item owned by a user, with pending status.
    """
    pending = models.BooleanField(default=False, db_index=True)
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='inventory_items'
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile.user.username} - {self.item}"
