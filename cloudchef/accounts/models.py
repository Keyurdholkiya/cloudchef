from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta

# TABLE 1: This stores basic login/account data for EVERYONE (Users and Chefs)
class chefsUser(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        VENDOR = "VENDOR", "Vendor"

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    email_token = models.CharField(max_length=100, null=True, blank=True)
    otp = models.CharField(max_length=10, null=True, blank=True)
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.CUSTOMER)
    notification_enabled = models.BooleanField(default=True)
    sound_theme = models.CharField(max_length=40, default="classic")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

# TABLE 2: This stores specific data ONLY for Chefs (Photos, Bio, Price)
class Chef(models.Model):
    # Links this specific chef data to a user account in the chefsUser table
    chef_owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="chef_profile"
    )
    chef_name = models.CharField(max_length=100)
    chef_slug = models.SlugField(max_length=140)
    chef_description = models.TextField()
    location = models.CharField(max_length=255)
    service_price = models.FloatField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.chef_name

# TABLE 3: This stores the multiple food photos for the Chef
class FoodImages(models.Model):
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name="food_images")
    image = models.ImageField(upload_to="food_images/")


class Dish(models.Model):
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name="dishes")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="dish_images/", null=True, blank=True)
    is_available = models.BooleanField(default=True)
    available_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.chef.chef_name})"

    @property
    def is_live_now(self):
        if not self.is_available:
            return False
        if not self.available_until:
            return True
        return self.available_until > timezone.now()

    @property
    def availability_minutes_left(self):
        if not self.available_until:
            return None
        remaining = int((self.available_until - timezone.now()).total_seconds() // 60)
        return max(0, remaining)

    def set_availability_window(self, hours=0, minutes=0):
        total_minutes = max(0, int(hours) * 60 + int(minutes))
        self.available_until = timezone.now() + timedelta(minutes=total_minutes) if total_minutes > 0 else None


class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items"
    )
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "dish")
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"{self.user.email} - {self.dish.name} x {self.quantity}"


class SavedAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_addresses"
    )
    label = models.CharField(max_length=80, default="Home")
    full_name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=15)
    address_line = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=120)
    pincode = models.CharField(max_length=12)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.label} - {self.address_line}"

    @property
    def map_query(self):
        parts = [self.address_line, self.landmark, self.city, self.state, self.pincode]
        return ", ".join([part for part in parts if part])


class Order(models.Model):
    class PaymentMethod(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        UPI = "UPI", "UPI"
        CARD = "CARD", "Card"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="orders")
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    delivery_name = models.CharField(max_length=120, blank=True)
    delivery_phone = models.CharField(max_length=15, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_map_query = models.CharField(max_length=255, blank=True)
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    delivery_notification_sent = models.BooleanField(default=False)
    review_prompt_disabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.dish.name}"

    @property
    def can_cancel(self):
        if self.is_cancelled:
            return False
        return (timezone.now() - self.created_at).total_seconds() <= 60


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ORDER = "order", "Order"
        PAYMENT = "payment", "Payment"
        DELIVERY = "delivery", "Delivery"

    class Scope(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        CHEF = "chef", "Chef"
        GLOBAL = "global", "Global"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=140)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20, choices=NotificationType.choices, default=NotificationType.INFO
    )
    scope = models.CharField(
        max_length=20, choices=Scope.choices, default=Scope.CUSTOMER
    )
    event_key = models.CharField(max_length=120, blank=True, null=True, unique=True)
    is_read = models.BooleanField(default=False)
    shown_in_browser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.user.email})"


class OrderReview(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="review")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="order_reviews"
    )
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="reviews")
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(default=5)
    feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.dish.name} ({self.rating}/5)"
