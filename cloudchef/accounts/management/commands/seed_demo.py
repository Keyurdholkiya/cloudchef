from decimal import Decimal
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Chef, Dish, Order, OrderReview, SavedAddress, chefsUser


class Command(BaseCommand):
    help = "Create demo Cloud Chef users, chefs, dishes, an order, and a review."

    def handle(self, *args, **options):
        with transaction.atomic():
            customer = self._user(
                email="customer@cloudchef.local",
                username="demo_customer",
                first_name="Demo",
                last_name="Customer",
                phone_number="9876543210",
                role=chefsUser.Role.CUSTOMER,
            )
            SavedAddress.objects.update_or_create(
                user=customer,
                label="Home",
                defaults={
                    "full_name": "Demo Customer",
                    "phone_number": "9876543210",
                    "address_line": "Navrangpura",
                    "landmark": "Near Stadium Circle",
                    "city": "Ahmedabad",
                    "state": "Gujarat",
                    "pincode": "380009",
                    "is_default": True,
                },
            )

            chef_specs = [
                {
                    "email": "asha@cloudchef.local",
                    "username": "chef_asha",
                    "name": "Asha's Gujarati Kitchen",
                    "phone": "9876543211",
                    "location": "Paldi, Ahmedabad, Gujarat 380007",
                    "description": "Comforting Gujarati thali, snacks, and daily home meals.",
                    "dishes": [
                        ("Gujarati Mini Thali", "Rotli, dal, shaak, rice, salad, and pickle.", "149.00"),
                        ("Methi Thepla Pack", "Soft thepla with curd and homemade chhundo.", "89.00"),
                    ],
                },
                {
                    "email": "imran@cloudchef.local",
                    "username": "chef_imran",
                    "name": "Imran's Tawa Specials",
                    "phone": "9876543212",
                    "location": "Vastrapur, Ahmedabad, Gujarat 380015",
                    "description": "Fresh tawa meals, rolls, and filling evening specials.",
                    "dishes": [
                        ("Paneer Tawa Roll", "Spiced paneer, onions, chutney, and soft paratha wrap.", "129.00"),
                        ("Veg Pulao Bowl", "Basmati rice cooked with vegetables, raita, and papad.", "119.00"),
                    ],
                },
                {
                    "email": "meera@cloudchef.local",
                    "username": "chef_meera",
                    "name": "Meera's Healthy Bowls",
                    "phone": "9876543213",
                    "location": "Satellite, Ahmedabad, Gujarat 380015",
                    "description": "Balanced homemade food for office lunches and light dinners.",
                    "dishes": [
                        ("Protein Khichdi Bowl", "Moong dal khichdi with vegetables, curd, and roasted papad.", "139.00"),
                        ("Millet Upma Box", "Light millet upma with coconut chutney and fruit.", "99.00"),
                    ],
                },
            ]

            created_dishes = []
            for spec in chef_specs:
                owner = self._user(
                    email=spec["email"],
                    username=spec["username"],
                    first_name=spec["name"].split()[0],
                    last_name="Chef",
                    phone_number=spec["phone"],
                    role=chefsUser.Role.VENDOR,
                )
                chef, _ = Chef.objects.update_or_create(
                    chef_owner=owner,
                    defaults={
                        "chef_name": spec["name"],
                        "chef_slug": f"{slugify(spec['name'])}-{owner.id}",
                        "chef_description": spec["description"],
                        "location": spec["location"],
                        "service_price": 30,
                        "is_active": True,
                    },
                )
                for name, description, price in spec["dishes"]:
                    dish, _ = Dish.objects.update_or_create(
                        chef=chef,
                        name=name,
                        defaults={
                            "description": description,
                            "price": Decimal(price),
                            "is_available": True,
                            "available_until": timezone.now() + timedelta(hours=8),
                        },
                    )
                    created_dishes.append(dish)

            sample_dish = created_dishes[0]
            order, _ = Order.objects.update_or_create(
                buyer=customer,
                dish=sample_dish,
                defaults={
                    "quantity": 1,
                    "total_amount": sample_dish.price,
                    "payment_method": Order.PaymentMethod.CARD,
                    "payment_status": Order.PaymentStatus.PAID,
                    "delivery_name": "Demo Customer",
                    "delivery_phone": "9876543210",
                    "delivery_address": "Navrangpura, Near Stadium Circle, Ahmedabad, Gujarat, 380009",
                    "delivery_map_query": "Navrangpura, Ahmedabad, Gujarat 380009",
                },
            )
            OrderReview.objects.update_or_create(
                order=order,
                defaults={
                    "user": customer,
                    "dish": sample_dish,
                    "chef": sample_dish.chef,
                    "rating": 5,
                    "feedback": "Fresh, neatly packed, and tasted exactly like homemade lunch.",
                },
            )

        self.stdout.write(self.style.SUCCESS("Demo marketplace created."))
        self.stdout.write("Customer login: customer@cloudchef.local / demo12345")
        self.stdout.write("Chef login: asha@cloudchef.local / demo12345")

    def _user(self, email, username, first_name, last_name, phone_number, role):
        user = chefsUser.objects.filter(email=email).first()
        created = False
        if user is None:
            user = chefsUser.objects.filter(phone_number=phone_number).first()
        if user is None:
            user = chefsUser(email=email)
            created = True
        user.email = email
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.phone_number = phone_number
        user.is_verified = True
        user.role = role
        user.save()
        if created or not user.check_password("demo12345"):
            user.set_password("demo12345")
            user.save(update_fields=["password"])
        return user
