from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

class HotelUser(AbstractUser):
    # Add a Role choice to distinguish between user types
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        VENDOR = "VENDOR", "Vendor"

    email = models.EmailField(unique=True)
    email_token = models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    otp = models.CharField(max_length=10, null=True, blank=True)
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.CUSTOMER)
    # Add business_name for vendors
    business_name = models.CharField(max_length=100, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

# Your other models (Ameneties, Hotel, etc.) remain the same
# Make sure the Hotel model's hotel_owner ForeignKey points to settings.AUTH_USER_MODEL
class Ameneties(models.Model):
    name = models.CharField(max_length=100)
    icon = models.ImageField(upload_to="ameneties_icons")
    def __str__(self):
        return self.name

class Hotel(models.Model):
    hotel_name = models.CharField(max_length=100)
    hotel_description = models.TextField()
    hotel_slug = models.SlugField(max_length=1000, unique=True)
    hotel_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hotels",
        limit_choices_to={'role': HotelUser.Role.VENDOR}
    )
    ameneties = models.ManyToManyField(Ameneties)
    hotel_price = models.FloatField()
    hotel_offer_price = models.FloatField(blank=True, null=True)
    hotel_location = models.TextField()
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.hotel_name

class HotelImages(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="hotel_images")
    image = models.ImageField(upload_to="hotel_images")

class HotelManager(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="hotel_managers")
    manager_name = models.CharField(max_length=100)
    manager_contact = models.CharField(max_length=100)
    def __str__(self):
        return self.manager_name