from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

# TABLE 1: This stores basic login/account data for EVERYONE (Users and Chefs)
class chefsUser(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        VENDOR = "VENDOR", "Vendor"

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    otp = models.CharField(max_length=10, null=True, blank=True)
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.CUSTOMER)

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