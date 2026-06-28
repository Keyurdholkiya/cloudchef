from django.test import TestCase
from django.urls import reverse

from .models import chefsUser


class SeparateLoginFlowTests(TestCase):
    def make_user(self, email, role):
        return chefsUser.objects.create_user(
            username=email, email=email, password="strong-pass-123", is_verified=True, role=role
        )

    def test_customer_cannot_login_on_chef_form(self):
        self.make_user("customer@example.com", chefsUser.Role.CUSTOMER)
        response = self.client.post(reverse("chef_login_page"), {
            "email": "customer@example.com", "password": "strong-pass-123"
        })
        self.assertRedirects(response, reverse("chef_register"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_chef_cannot_login_on_customer_form(self):
        self.make_user("chef@example.com", chefsUser.Role.VENDOR)
        response = self.client.post(reverse("login_page"), {
            "email": "chef@example.com", "password": "strong-pass-123"
        })
        self.assertRedirects(response, reverse("chef_login_page"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_chef_login_opens_console_setup(self):
        self.make_user("chef@example.com", chefsUser.Role.VENDOR)
        response = self.client.post(reverse("chef_login_page"), {
            "email": "chef@example.com", "password": "strong-pass-123"
        })
        self.assertRedirects(response, reverse("chef_side"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["chef_user_id"], chefsUser.objects.get(email="chef@example.com").id)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_customer_stays_logged_in_after_chef_login(self):
        customer = self.make_user("customer@example.com", chefsUser.Role.CUSTOMER)
        chef = self.make_user("chef@example.com", chefsUser.Role.VENDOR)
        self.client.force_login(customer)
        self.client.post(reverse("chef_login_page"), {
            "email": chef.email, "password": "strong-pass-123"
        })
        self.assertEqual(int(self.client.session["_auth_user_id"]), customer.id)
        self.assertEqual(self.client.session["chef_user_id"], chef.id)

    def test_chef_registration_creates_vendor(self):
        response = self.client.post(reverse("chef_register"), {
            "first_name": "Test", "last_name": "Chef", "email": "newchef@example.com",
            "phone_number": "9999999999", "password": "strong-pass-123",
        })
        self.assertRedirects(response, reverse("chef_login_page"))
        self.assertEqual(chefsUser.objects.get(email="newchef@example.com").role, chefsUser.Role.VENDOR)

# Create your tests here.
