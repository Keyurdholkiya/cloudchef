from django.shortcuts import render, redirect, HttpResponse
from django.db.models import Q
from django.db.models import Sum
from django.contrib import messages
from django.conf import settings
from .utils import generateRandomToken, sendEmailToken
from django.contrib.auth import authenticate, login, logout
import random
from .utils import sendOTPtoEmail
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.text import slugify
from urllib.parse import quote
from datetime import timedelta
from .models import chefsUser, Chef, FoodImages, Dish, Order
from home.notification_service import notify_login_welcome

THEME_OPTIONS = [
    ("light", "Classic Spice", "Warm cream with tomato red highlights"),
    ("dark", "Midnight Tandoor", "Rich dark mode with ember accents"),
    ("sunset", "Sunset Feast", "Soft peach and saffron glow"),
    ("forest", "Herbal Garden", "Fresh green and earthy neutrals"),
    ("ocean", "Ocean Breeze", "Cool aqua and clean blue depth"),
    ("royal", "Royal Thali", "Luxury navy with golden shine"),
    ("rose", "Rose Dessert", "Elegant blush pink and cherry tones"),
    ("midnight", "Midnight Neon", "Bold night mode with vivid contrast"),
    ("mint", "Mint Fresh", "Light mint palette with airy surfaces"),
    ("latte", "Cafe Latte", "Coffee beige with cozy brown warmth"),
]


def _build_unique_chef_slug(chef_name, user_id):
    base = slugify(chef_name) or "chef"
    return f"{base}-{user_id}"


def _safe_theme(theme_name):
    valid_themes = {name for name, _, _ in THEME_OPTIONS}
    return theme_name if theme_name in valid_themes else "light"


def _theme_label(theme_name):
    return dict((name, label) for name, label, _ in THEME_OPTIONS).get(theme_name, "Classic Spice")


def _build_full_location_from_request(request):
    address_line = request.POST.get("address_line", "").strip()
    landmark = request.POST.get("landmark", "").strip()
    city = request.POST.get("city", "").strip()
    state = request.POST.get("state", "").strip()
    pincode = request.POST.get("pincode", "").strip()
    fallback = request.POST.get("location", "").strip()
    parts = [address_line, landmark, city, state, pincode]
    full_location = ", ".join([part for part in parts if part])
    return full_location or fallback


def _prepare_fresh_session_for_user_login(request, user):
    previous_user_id = request.session.get("_auth_user_id")
    if previous_user_id and str(previous_user_id) != str(user.id):
        for key in ["cart", "last_order_ids", "login_mode"]:
            request.session.pop(key, None)
        request.session.modified = True


def login_page(request):
    if request.method == "POST":
        email = (request.POST.get('email') or "").strip().lower()
        password = request.POST.get('password') or ""
        next_url = request.POST.get('next') or request.GET.get('next')

        chef_user_qs = chefsUser.objects.filter(email=email)

        if not chef_user_qs.exists():
            messages.info(request, "Account not found. Please register first.")
            return redirect(f'/accounts/register/?email={quote(email)}')

        chef_user = chef_user_qs.first()

        if not chef_user.is_verified:
            if settings.DEBUG:
                chef_user.is_verified = True
                chef_user.save(update_fields=["is_verified"])
                messages.info(request, "Dev mode: account auto-verified.")
            else:
                messages.warning(request, "Account not verified. Please check your email.")
                return redirect('/accounts/login/')

        # Custom user model uses email as USERNAME_FIELD.
        user = authenticate(request, email=email, password=password)
        if not user:
            fallback_user = chef_user_qs.first()
            if fallback_user and fallback_user.check_password(password):
                user = fallback_user

        if user:
            _prepare_fresh_session_for_user_login(request, user)
            login(request, user)
            request.session["login_mode"] = "customer"
            notify_login_welcome(user)
            messages.success(request, "Login Successful!")
            return redirect(next_url or '/')

        messages.warning(request, "Invalid credentials.")
        return redirect('/accounts/login/')

    return render(request, 'accounts/login.html')


def chef_login_page(request):
    if request.method == "POST":
        email = (request.POST.get('email') or "").strip().lower()
        password = request.POST.get('password') or ""
        next_url = request.POST.get('next') or request.GET.get('next')

        chef_user_qs = chefsUser.objects.filter(email=email)
        if not chef_user_qs.exists():
            messages.info(request, "Chef account not found. Please register first.")
            return redirect(f'/accounts/register/?email={quote(email)}')

        chef_user = chef_user_qs.first()
        if not chef_user.is_verified:
            if settings.DEBUG:
                chef_user.is_verified = True
                chef_user.save(update_fields=["is_verified"])
            else:
                messages.warning(request, "Account not verified.")
                return redirect('/accounts/chef-login/')

        user = authenticate(request, email=email, password=password)
        if not user:
            fallback_user = chef_user_qs.first()
            if fallback_user and fallback_user.check_password(password):
                user = fallback_user
        if user:
            _prepare_fresh_session_for_user_login(request, user)
            login(request, user)
            request.session["login_mode"] = "chef"
            notify_login_welcome(user)
            messages.success(request, "Chef login successful.")
            return redirect(next_url or '/accounts/chef-side/')

        messages.warning(request, "Invalid credentials.")
        return redirect('/accounts/chef-login/')

    return render(request, 'accounts/chef_login.html')

def register(request):
    prefill_email = request.GET.get("email", "")
    if request.user.is_authenticated:
        logout(request)

    if request.method == "POST":
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = (request.POST.get('email') or "").strip().lower()
        password = request.POST.get('password') or ""
        phone_number = (request.POST.get('phone_number') or "").strip()

        if chefsUser.objects.filter(Q(email=email) | Q(phone_number=phone_number)).exists():
            messages.warning(request, "An account already exists with this Email or Phone Number.")
            return redirect('/accounts/register/')

        chef_user = chefsUser.objects.create(
            username=(phone_number or email),
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            email_token=generateRandomToken(),
            is_verified=True,
        )
        chef_user.set_password(password)
        chef_user.save()

        try:
            sendEmailToken(email, chef_user.email_token)
            messages.success(request, "Registration successful.")
        except Exception:
            messages.info(request, "Registered successfully. Email service not configured.")

        return redirect('/accounts/login/')

    return render(request, 'accounts/register.html', {"prefill_email": prefill_email})

def verify_email_token(request, token):
    try:
        chef_user = chefsUser.objects.get(email_token=token)
        chef_user.is_verified = True
        chef_user.save()
        messages.success(request, "Your email has been successfully verified. You can now log in.")
        return redirect('/accounts/login/')
    except chefsUser.DoesNotExist:
        return HttpResponse("<h2>Invalid Token or user does not exist.</h2>")
      
      

def send_otp(request, email):
    # Use .first() to get a single object or None
    chef_user = chefsUser.objects.filter(email=email).first()

    if not chef_user:
        messages.warning(request, "No account found with that email.")
        return redirect('/accounts/login/')

    # Generate a random 4-digit OTP
    otp = random.randint(1000, 9999)
    chef_user.otp = otp
    chef_user.save()  # Save the OTP to the user's record

    try:
        sendOTPtoEmail(email, otp)
        messages.success(request, f"An OTP has been sent to {email}.")
    except Exception:
        if settings.DEBUG:
            messages.info(request, f"Dev mode OTP for {email}: {otp}")
        else:
            messages.warning(request, "Failed to send OTP email. Please try again.")
    # Redirect to the verification page, passing the email in the URL
    return redirect(f'/accounts/verify-otp/{email}/')


# accounts/views.py

def verify_otp(request, email):
    if request.method == "POST":
        otp = request.POST.get('otp')
        chef_user = chefsUser.objects.get(email=email) # Using your new model name

        if otp == chef_user.otp:
            login(request, chef_user)
            notify_login_welcome(chef_user)
            messages.success(request, "Verification Successful!")
            # Redirect to profile setup instead of home
            return redirect('chef_profile_setup') 
        else:
            messages.warning(request, "Wrong OTP.")
            return redirect('verify_otp', email=email)
    
    return render(request, 'verify_otp.html', {'email': email})


@login_required
def chef_logout(request):
    request.session.pop("login_mode", None)
    messages.success(request, "Chef panel logout successful.")
    return redirect('/')

@login_required
def chef_profile_setup(request):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-setup/')

    if request.method == "POST":
        chef_name = request.POST.get('chef_name')
        description = request.POST.get('description')
        location = _build_full_location_from_request(request)
        price = request.POST.get('price')
        images = request.FILES.getlist('food_images')

        chef, _ = Chef.objects.update_or_create(
            chef_owner=request.user,
            defaults={
                'chef_name': chef_name,
                'chef_slug': _build_unique_chef_slug(chef_name, request.user.id),
                'chef_description': description,
                'location': location,
                'service_price': price,
            }
        )

        for img in images:
            FoodImages.objects.create(chef=chef, image=img)

        messages.success(request, "Chef profile created successfully!")
        return redirect('chef_side')

    return render(request, 'chef_profile_setup.html')

def _chef_dashboard_context(request):
    search_query = (request.GET.get("q") or "").strip()
    chef_profile = Chef.objects.filter(chef_owner=request.user).first()
    dishes = Dish.objects.filter(chef=chef_profile).order_by('-id') if chef_profile else Dish.objects.none()
    live_dishes = dishes.filter(
        is_available=True
    ).filter(
        Q(available_until__isnull=True) | Q(available_until__gt=timezone.now())
    ) if chef_profile else Dish.objects.none()
    all_orders_qs = Order.objects.filter(dish__chef=chef_profile).select_related('buyer', 'dish') if chef_profile else Order.objects.none()

    if search_query:
        dishes = dishes.filter(name__icontains=search_query)
        live_dishes = live_dishes.filter(name__icontains=search_query)
        all_orders_qs = all_orders_qs.filter(
            Q(dish__name__icontains=search_query)
            | Q(buyer__first_name__icontains=search_query)
            | Q(buyer__last_name__icontains=search_query)
            | Q(buyer__email__icontains=search_query)
        )

    total_orders = all_orders_qs.count()
    today = timezone.localdate()
    month_start = today.replace(day=1)
    today_orders_qs = all_orders_qs.filter(created_at__date=today)
    orders_today = today_orders_qs.count()
    earnings_today = today_orders_qs.aggregate(total=Sum('total_amount')).get('total') or 0
    recent_orders = all_orders_qs.order_by('-id')[:3]
    total_earnings = all_orders_qs.aggregate(total=Sum('total_amount')).get('total') or 0
    month_earnings = all_orders_qs.filter(created_at__date__gte=month_start).aggregate(total=Sum('total_amount')).get('total') or 0
    profit_earnings = all_orders_qs.filter(payment_status=Order.PaymentStatus.PAID).aggregate(total=Sum('total_amount')).get('total') or 0
    loss_earnings = all_orders_qs.filter(payment_status=Order.PaymentStatus.PENDING).aggregate(total=Sum('total_amount')).get('total') or 0

    top_dishes = (
        dishes.annotate(order_count=Sum('orders__quantity'), earning=Sum('orders__total_amount'))
        .order_by('-earning', '-id')[:5]
    )

    max_metric = max(
        float(total_earnings or 0),
        float(month_earnings or 0),
        float(profit_earnings or 0),
        float(loss_earnings or 0),
        1.0,
    )
    earnings_graph = [
        {
            'label': 'Total Earn',
            'value': total_earnings,
            'width': round((float(total_earnings) / max_metric) * 100),
            'class_name': 'bar-total',
        },
        {
            'label': 'Month Earn',
            'value': month_earnings,
            'width': round((float(month_earnings) / max_metric) * 100),
            'class_name': 'bar-month',
        },
        {
            'label': 'Profit',
            'value': profit_earnings,
            'width': round((float(profit_earnings) / max_metric) * 100),
            'class_name': 'bar-profit',
        },
        {
            'label': 'Loss',
            'value': loss_earnings,
            'width': round((float(loss_earnings) / max_metric) * 100),
            'class_name': 'bar-loss',
        },
    ]

    max_dish_earning = max([float(getattr(item, 'earning', 0) or 0) for item in top_dishes] + [1.0])
    top_dish_graph = [
        {
            'name': item.name,
            'value': item.earning or 0,
            'width': round((float(item.earning or 0) / max_dish_earning) * 100),
            'order_count': item.order_count or 0,
        }
        for item in top_dishes
    ]

    profit_percent = round((float(profit_earnings or 0) / max(float(total_earnings or 0), 1.0)) * 100)
    month_percent = round((float(month_earnings or 0) / max(float(total_earnings or 0), 1.0)) * 100)

    return {
        'chef_profile': chef_profile,
        'dishes': dishes,
        'live_dishes': live_dishes,
        'live_dishes_count': live_dishes.count(),
        'total_dishes_count': dishes.count(),
        'dashboard_live_dishes_count': 0,
        'dashboard_total_dishes_count': 0,
        'dashboard_total_orders': 0,
        'dashboard_orders_today': 0,
        'dashboard_earnings_today': 0,
        'dashboard_total_earnings': 0,
        'all_orders': all_orders_qs,
        'total_orders': total_orders,
        'orders_today': orders_today,
        'earnings_today': earnings_today,
        'recent_orders': recent_orders,
        'top_dishes': top_dishes,
        'total_earnings': total_earnings,
        'month_earnings': month_earnings,
        'profit_earnings': profit_earnings,
        'loss_earnings': loss_earnings,
        'earnings_graph': earnings_graph,
        'top_dish_graph': top_dish_graph,
        'profit_percent': profit_percent,
        'month_percent': month_percent,
        'search_query': search_query,
    }


def _dish_availability_deadline(hours_value, minutes_value):
    try:
        hours = max(0, int(hours_value or 0))
    except (TypeError, ValueError):
        hours = 0
    try:
        minutes = max(0, int(minutes_value or 0))
    except (TypeError, ValueError):
        minutes = 0

    total_minutes = (hours * 60) + minutes
    if total_minutes <= 0:
        return None, 0
    return timezone.now() + timedelta(minutes=total_minutes), total_minutes

@login_required
def chef_side(request):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/')

    context = _chef_dashboard_context(request)
    if not context['chef_profile']:
        return redirect('chef_profile_setup')
    context['active_page'] = 'dashboard'
    return render(request, 'chef_side.html', context)


@login_required
def chef_my_dishes(request):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/my-dishes/')

    context = _chef_dashboard_context(request)
    if not context['chef_profile']:
        return redirect('chef_profile_setup')
    context['dishes'] = context['live_dishes']
    context['active_page'] = 'my_dishes'
    return render(request, 'chef_my_dishes.html', context)


@login_required
def chef_orders(request):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/orders/')

    context = _chef_dashboard_context(request)
    if not context['chef_profile']:
        return redirect('chef_profile_setup')
    context['active_page'] = 'orders'
    return render(request, 'chef_orders.html', context)


@login_required
def remove_chef_order(request, order_id):
    if request.method != "POST":
        return redirect('chef_orders')
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/orders/')

    chef_profile = Chef.objects.filter(chef_owner=request.user).first()
    if not chef_profile:
        return redirect('chef_profile_setup')

    order = Order.objects.filter(id=order_id, dish__chef=chef_profile).first()
    if not order:
        messages.warning(request, "Order not found.")
        return redirect('chef_orders')

    order.delete()
    messages.success(request, "Order removed successfully.")
    return redirect('chef_orders')


@login_required
def clear_chef_orders(request):
    if request.method != "POST":
        return redirect('chef_orders')
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/orders/')

    chef_profile = Chef.objects.filter(chef_owner=request.user).first()
    if not chef_profile:
        return redirect('chef_profile_setup')

    deleted_count, _ = Order.objects.filter(dish__chef=chef_profile).delete()
    if deleted_count:
        messages.success(request, "All chef orders cleared successfully.")
    else:
        messages.info(request, "No orders available to clear.")
    return redirect('chef_orders')


@login_required
def chef_earnings(request):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/earnings/')

    context = _chef_dashboard_context(request)
    if not context['chef_profile']:
        return redirect('chef_profile_setup')
    context['active_page'] = 'earnings'
    return render(request, 'chef_earnings.html', context)


@login_required
def chef_profile(request):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/profile/')

    context = _chef_dashboard_context(request)
    chef_profile = context['chef_profile']

    if request.method == "POST":
        action = request.POST.get("action", "profile")

        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        chef_name = request.POST.get('chef_name')
        location = _build_full_location_from_request(request)
        price = request.POST.get('price')
        description = request.POST.get('description')

        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.phone_number = phone_number
        request.user.save(update_fields=['first_name', 'last_name', 'phone_number'])

        if chef_profile:
            chef_profile.chef_name = chef_name
            chef_profile.chef_slug = _build_unique_chef_slug(chef_name, request.user.id)
            chef_profile.location = location
            chef_profile.service_price = price
            chef_profile.chef_description = description
            chef_profile.save()
        else:
            chef_profile = Chef.objects.create(
                chef_owner=request.user,
                chef_name=chef_name,
                chef_slug=_build_unique_chef_slug(chef_name, request.user.id),
                location=location,
                service_price=price or 0,
                chef_description=description or "",
            )

        messages.success(request, "Profile updated successfully.")
        return redirect('chef_profile')

    context = _chef_dashboard_context(request)
    context['active_page'] = 'profile'
    return render(request, 'chef_profile.html', context)


@login_required
def add_dish(request):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/add-dish/')

    context = _chef_dashboard_context(request)
    chef_profile = context['chef_profile']

    if not chef_profile:
        messages.warning(request, "Please complete chef profile setup first.")
        return redirect('chef_profile_setup')

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        price = request.POST.get("price")
        image = request.FILES.get("image")
        is_available = request.POST.get("is_available", "on") == "on"
        available_until, total_minutes = _dish_availability_deadline(
            request.POST.get("availability_hours"),
            request.POST.get("availability_minutes"),
        )

        if total_minutes <= 0:
            messages.warning(request, "Please set how long this dish should stay live.")
            context['active_page'] = 'add_dish'
            context['dish_form'] = {
                "name": name,
                "description": description,
                "price": price,
                "availability_hours": request.POST.get("availability_hours", "0"),
                "availability_minutes": request.POST.get("availability_minutes", "0"),
            }
            return render(request, "chef_add_dish.html", context)

        Dish.objects.create(
            chef=chef_profile,
            name=name,
            description=description,
            price=price,
            image=image,
            is_available=is_available,
            available_until=available_until,
        )

        messages.success(request, f"Dish added successfully. It will stay live for {total_minutes} minutes.")
        return redirect('chef_my_dishes')

    context['active_page'] = 'add_dish'
    context['dish_form'] = {
        "availability_hours": "1",
        "availability_minutes": "0",
    }
    return render(request, "chef_add_dish.html", context)


@login_required
def remove_dish(request, dish_id):
    if request.session.get("login_mode") != "chef":
        messages.info(request, "Please login from Chef Login to access chef-side.")
        return redirect('/accounts/chef-login/?next=/accounts/chef-side/my-dishes/')

    if request.method != "POST":
        return redirect("chef_my_dishes")

    chef_profile = Chef.objects.filter(chef_owner=request.user).first()
    dish = Dish.objects.filter(id=dish_id, chef=chef_profile).first()
    if not dish:
        messages.warning(request, "Dish not found.")
        return redirect("chef_my_dishes")

    dish.is_available = False
    dish.available_until = timezone.now()
    dish.save(update_fields=["is_available", "available_until"])
    messages.success(request, f"{dish.name} removed from shop successfully.")
    return redirect("chef_my_dishes")
