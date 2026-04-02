from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
import json
import math
from zoneinfo import ZoneInfo
from accounts.models import Dish, Order, SavedAddress, Notification, OrderReview, CartItem
from .notification_service import notify_order_placed, notify_payment_success, notify_chef_order_placed, build_whatsapp_link, sync_delivery_notifications
from django.db.models import Q

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

SOUND_OPTIONS = [
    ("classic", "Classic Bell", "Balanced Cloud Chef default"),
    ("spice", "Spice Pop", "Bright and energetic"),
    ("soft", "Soft Bloom", "Gentle and calm"),
    ("royal", "Royal Chime", "Premium layered tone"),
    ("mint", "Mint Drop", "Fresh and clean"),
    ("sunset", "Sunset Pulse", "Warm and smooth"),
    ("neon", "Neon Ping", "Sharp modern feedback"),
    ("lofi", "Lo-Fi Tap", "Low-key mellow tone"),
    ("glass", "Glass Spark", "Light crystal touch"),
    ("drum", "Food Beat", "Punchy playful pulse"),
]

TEMP_HIDE_SHOP_ITEMS = False


def _safe_theme(theme_name):
    valid_themes = {name for name, _, _ in THEME_OPTIONS}
    return theme_name if theme_name in valid_themes else "light"


def _theme_label(theme_name):
    return dict((name, label) for name, label, _ in THEME_OPTIONS).get(theme_name, "Classic Spice")


_GEOCODE_CACHE = {}
_DISTANCE_CACHE = {}


def _geocode_location(query):
    query = (query or "").strip()
    if not query:
        return None
    if query in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[query]
    try:
        request = Request(
            "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=" + urlencode({"q": query})[2:],
            headers={"User-Agent": "CloudChef/1.0"},
        )
        with urlopen(request, timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload:
            coords = (float(payload[0]["lat"]), float(payload[0]["lon"]))
            _GEOCODE_CACHE[query] = coords
            return coords
    except (URLError, ValueError, KeyError, json.JSONDecodeError):
        return None
    return None


def _distance_km(origin, destination):
    cache_key = ((origin or "").strip().lower(), (destination or "").strip().lower())
    if cache_key in _DISTANCE_CACHE:
        return _DISTANCE_CACHE[cache_key]
    origin_coords = _geocode_location(origin)
    destination_coords = _geocode_location(destination)
    if not origin_coords or not destination_coords:
        return None
    lat1, lon1 = origin_coords
    lat2, lon2 = destination_coords
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    distance = round(radius * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))), 1)
    _DISTANCE_CACHE[cache_key] = distance
    return distance


def _route_map_url(origin, destination):
    origin_q = urlencode({"q": origin})[2:]
    destination_q = urlencode({"q": destination})[2:]
    return f"https://maps.google.com/maps?saddr={origin_q}&daddr={destination_q}&output=embed"


def _fallback_map_embed_url(query):
    safe_query = urlencode({"q": query or "Ahmedabad"})[2:]
    return f"https://maps.google.com/maps?q={safe_query}&t=&z=13&ie=UTF8&iwloc=&output=embed"


def _delivery_eta_from_distance(distance_km):
    if not distance_km:
        return 5
    return max(5, min(35, int(round(distance_km * 4))))


def _india_now():
    return timezone.now().astimezone(ZoneInfo("Asia/Kolkata"))


def _available_dishes_queryset():
    if TEMP_HIDE_SHOP_ITEMS:
        return Dish.objects.none()
    now = timezone.now()
    return Dish.objects.filter(
        is_available=True
    ).filter(
        Q(available_until__isnull=True) | Q(available_until__gt=now)
    ).exclude(
        name__icontains="gota"
    )


def _featured_dishes_queryset():
    return _available_dishes_queryset().select_related('chef').order_by('-id')[:12]


def _merge_session_cart_to_db(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return
    session_cart = request.session.get("cart", {}) or {}
    if not session_cart:
        return

    valid_dishes = {}
    for dish_id, qty in session_cart.items():
        try:
            dish_id_int = int(dish_id)
            qty_int = int(qty)
        except (TypeError, ValueError):
            continue
        if qty_int > 0:
            valid_dishes[dish_id_int] = qty_int

    if not valid_dishes:
        request.session["cart"] = {}
        request.session.modified = True
        return

    live_dishes = {dish.id: dish for dish in _available_dishes_queryset().filter(id__in=valid_dishes.keys())}
    existing = {item.dish_id: item for item in CartItem.objects.filter(user=request.user, dish_id__in=live_dishes.keys())}

    for dish_id, qty in valid_dishes.items():
        if dish_id not in live_dishes:
            continue
        item = existing.get(dish_id)
        if item:
            item.quantity += qty
            item.save(update_fields=["quantity", "updated_at"])
        else:
            CartItem.objects.create(user=request.user, dish_id=dish_id, quantity=qty)

    request.session["cart"] = {}
    request.session.modified = True


def _cart_count_for_request(request):
    if getattr(request, "user", None) and request.user.is_authenticated:
        _merge_session_cart_to_db(request)
        return sum(item.quantity for item in CartItem.objects.filter(user=request.user).only("quantity"))
    return _cart_count(_get_cart(request))


def _home_order_context(user):
    latest_order = None
    latest_order_status = None
    latest_order_link = None
    latest_order_meta = None
    pending_review_order = None
    latest_order_customer_name = user.first_name if user and user.is_authenticated else ""

    if user and user.is_authenticated:
        user_orders = list(
            Order.objects.filter(buyer=user)
            .select_related("dish", "dish__chef")
            .order_by("-id")[:8]
        )
        latest_order = user_orders[0] if user_orders else None
        if latest_order:
            chef_location = ""
            if getattr(latest_order.dish, "chef", None):
                chef_location = getattr(latest_order.dish.chef, "location", "") or ""
            customer_location = (
                getattr(latest_order, "delivery_address", "") or
                getattr(latest_order, "address", "") or
                ""
            )
            eta_total_minutes = _delivery_eta_from_distance(_distance_km(chef_location, customer_location))
            elapsed_seconds = max(0, int((timezone.now() - latest_order.created_at).total_seconds()))
            elapsed_mins = elapsed_seconds // 60
            remaining_mins = max(0, eta_total_minutes - elapsed_mins)
            progress_percent = min(100, max(6, int(round((elapsed_seconds / max(eta_total_minutes * 60, 1)) * 100))))

            if latest_order.is_cancelled:
                latest_order = None
            elif remaining_mins <= 0:
                latest_order = None
            elif remaining_mins <= 1:
                latest_order_status = "Reached nearby"
                stage_key = "nearby"
            elif elapsed_mins < max(2, eta_total_minutes // 4):
                latest_order_status = "Order confirmed"
                stage_key = "confirmed"
            elif elapsed_mins < max(4, eta_total_minutes // 2):
                latest_order_status = "Chef is preparing"
                stage_key = "preparing"
            elif elapsed_mins < max(5, int(eta_total_minutes * 0.75)):
                latest_order_status = "Rider picked your order"
                stage_key = "picked"
            else:
                latest_order_status = "On the way"
                stage_key = "ontheway"
            if latest_order:
                latest_order_link = f"/shop/order-success/{latest_order.id}/"
                latest_order_meta = {
                    "eta_minutes": remaining_mins,
                    "progress_percent": progress_percent,
                    "stage_key": stage_key,
                    "created_at": latest_order.created_at.isoformat(),
                    "total_eta_minutes": eta_total_minutes,
                }

        reviewed_order_ids = set(
            OrderReview.objects.filter(user=user).values_list("order_id", flat=True)
        )
        for order in user_orders:
            if order.is_cancelled or order.review_prompt_disabled or order.id in reviewed_order_ids:
                continue
            chef_location = getattr(order.dish.chef, "location", "") if getattr(order.dish, "chef", None) else ""
            customer_location = (
                getattr(order, "delivery_address", "") or
                getattr(order, "address", "") or
                ""
            )
            eta_total_minutes = _delivery_eta_from_distance(_distance_km(chef_location, customer_location))
            elapsed_mins = int((timezone.now() - order.created_at).total_seconds() // 60)
            if elapsed_mins >= eta_total_minutes:
                pending_review_order = order
                break

    return {
        "latest_order": latest_order,
        "latest_order_status": latest_order_status,
        "latest_order_link": latest_order_link,
        "latest_order_customer_name": latest_order_customer_name,
        "latest_order_meta": latest_order_meta,
        "pending_review_order": pending_review_order,
    }


def distance_preview(request):
    origin = (request.GET.get("origin") or "").strip()
    destination = (request.GET.get("destination") or "").strip()
    if not origin or not destination:
        return JsonResponse({"ok": False, "message": "Missing origin or destination."}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "distance_km": _distance_km(origin, destination),
            "route_map_url": _route_map_url(origin, destination),
        }
    )


def index(request):
    featured_dishes = _featured_dishes_queryset()
    customer_reviews = []
    order_context = _home_order_context(request.user)

    return render(
        request,
        'index.html',
        {
            "featured_dishes": featured_dishes,
            "customer_reviews": customer_reviews,
            **order_context,
        },
    )

def login_page(request):
    return redirect('/accounts/login/')

def register(request):
    return redirect('/accounts/register/')

def logout_user(request):
    if request.user.is_authenticated:
        messages.success(request, "Logged out successfully.")
    logout(request)
    return redirect('/')


@login_required
def customer_settings(request):
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "profile":
            request.user.first_name = request.POST.get("first_name", "").strip()
            request.user.last_name = request.POST.get("last_name", "").strip()
            request.user.phone_number = request.POST.get("phone_number", "").strip()
            request.user.save(update_fields=["first_name", "last_name", "phone_number"])
            messages.success(request, "Profile updated successfully.")
            return redirect("customer_settings")

        if action == "notifications":
            request.user.notification_enabled = request.POST.get("notification_enabled") == "on"
            request.user.save(update_fields=["notification_enabled"])
            messages.success(
                request,
                "Notifications turned on." if request.user.notification_enabled else "Notifications turned off.",
            )
            return redirect("customer_settings")

        if action == "theme":
            theme = _safe_theme(request.POST.get("theme", "light").strip())
            request.session["site_theme"] = theme
            request.session["theme_toast"] = f"{_theme_label(theme)} theme applied"
            request.session.modified = True
            return redirect("customer_settings")

        if action == "sound":
            valid_sounds = {name for name, _, _ in SOUND_OPTIONS}
            sound_theme = (request.POST.get("sound_theme") or "classic").strip().lower()
            if sound_theme not in valid_sounds:
                sound_theme = "classic"
            request.user.sound_theme = sound_theme
            request.user.save(update_fields=["sound_theme"])
            messages.success(request, f"{dict((name, label) for name, label, _ in SOUND_OPTIONS).get(sound_theme, 'Classic Bell')} sound selected.")
            return redirect("customer_settings")

    current_theme = _safe_theme(request.session.get("site_theme", "light"))
    return render(
        request,
        "customer_settings.html",
        {
            "current_theme": current_theme,
            "theme_options": THEME_OPTIONS,
            "current_sound_theme": getattr(request.user, "sound_theme", "classic") or "classic",
            "sound_options": SOUND_OPTIONS,
        },
    )

def dashboard(request):
    return render(request, 'dashboard.html')

def help(request):
    return render(request, 'help.html')

# def contactus(request):
#     return render(request, 'contactus.html')

def aboutus(request):
    return render(request, 'aboutus.html')

def services(request):
    return render(request, 'services.html')

def blog(request):
    return render(request, 'blog.html')

def careers(request):
    return render(request, 'careers.html')

def privacy_policy(request):
    return render(request, 'privacy_policy.html')

def events(request):
    return render(request, 'events.html')

def shop(request):
    dishes = _available_dishes_queryset().select_related('chef').order_by('-id')
    search = request.GET.get("search")
    if search:
        dishes = dishes.filter(name__icontains=search)
    return render(request, 'shop.html', {"dishes": dishes, "search": search or ""})


def _get_cart(request):
    return request.session.setdefault("cart", {})


def _cart_items_with_total(request):
    if getattr(request, "user", None) and request.user.is_authenticated:
        _merge_session_cart_to_db(request)
        cart_items = list(
            CartItem.objects.filter(user=request.user)
            .select_related("dish", "dish__chef")
            .order_by("-updated_at", "-id")
        )
        items = []
        total = 0
        stale_item_ids = []
        for cart_item in cart_items:
            dish = cart_item.dish
            if not dish or not dish.is_live_now:
                stale_item_ids.append(cart_item.id)
                continue
            line_total = dish.price * cart_item.quantity
            total += line_total
            items.append({
                "dish": dish,
                "quantity": cart_item.quantity,
                "line_total": line_total,
            })
        if stale_item_ids:
            CartItem.objects.filter(id__in=stale_item_ids).delete()
        return items, total

    cart = _get_cart(request)
    dish_ids = [int(i) for i in cart.keys()]
    dishes = _available_dishes_queryset().filter(id__in=dish_ids).select_related('chef')
    dish_map = {d.id: d for d in dishes}

    items = []
    total = 0
    cart_changed = False
    for dish_id_str, qty in cart.items():
        dish_id = int(dish_id_str)
        dish = dish_map.get(dish_id)
        if not dish:
            cart.pop(dish_id_str, None)
            cart_changed = True
            continue
        line_total = dish.price * qty
        total += line_total
        items.append({
            "dish": dish,
            "quantity": qty,
            "line_total": line_total,
        })
    if cart_changed:
        request.session["cart"] = cart
        request.session.modified = True
    return items, total


def _cart_count(cart):
    count = 0
    for qty in cart.values():
        try:
            count += int(qty)
        except (TypeError, ValueError):
            continue
    return count


def _saved_addresses_for_user(user):
    return SavedAddress.objects.filter(user=user).order_by("-is_default", "-id")


def _serialize_addresses(addresses):
    items = []
    for address in addresses:
        items.append(
            {
                "id": address.id,
                "label": address.label,
                "full_name": address.full_name,
                "phone_number": address.phone_number,
                "address_line": address.address_line,
                "landmark": address.landmark,
                "city": address.city,
                "state": address.state,
                "pincode": address.pincode,
                "map_query": address.map_query,
            }
        )
    return items


def _default_address_data(user, addresses, preferred_address_id=None):
    default_address = None
    if preferred_address_id:
        default_address = next((address for address in addresses if str(address.id) == str(preferred_address_id)), None)
    if default_address is None:
        default_address = addresses[0] if addresses else None
    if default_address:
        return {
            "selected_address_id": default_address.id,
            "label": default_address.label,
            "full_name": default_address.full_name,
            "phone_number": default_address.phone_number,
            "address_line": default_address.address_line,
            "landmark": default_address.landmark,
            "city": default_address.city,
            "state": default_address.state,
            "pincode": default_address.pincode,
            "save_address": True,
            "map_query": default_address.map_query,
        }
    return {
        "selected_address_id": "",
        "label": "Home",
        "full_name": user.get_full_name().strip() or user.first_name or "",
        "phone_number": user.phone_number or "",
        "address_line": "",
        "landmark": "",
        "city": "",
        "state": "",
        "pincode": "",
        "save_address": True,
        "map_query": "Ahmedabad",
    }


def _address_payload_from_post(request, user, addresses):
    selected_address_id = (request.POST.get("selected_address_id") or "").strip()
    payload = {
        "selected_address_id": selected_address_id,
        "label": request.POST.get("label", "Home").strip() or "Home",
        "full_name": request.POST.get("full_name", "").strip(),
        "phone_number": request.POST.get("phone_number", "").strip(),
        "address_line": request.POST.get("address_line", "").strip(),
        "landmark": request.POST.get("landmark", "").strip(),
        "city": request.POST.get("city", "").strip(),
        "state": request.POST.get("state", "").strip(),
        "pincode": request.POST.get("pincode", "").strip(),
        "save_address": request.POST.get("save_address") == "on",
    }
    parts = [payload["address_line"], payload["landmark"], payload["city"], payload["state"], payload["pincode"]]
    payload["map_query"] = ", ".join([part for part in parts if part]) or "Ahmedabad"
    return payload


def _validate_address_payload(payload):
    required_fields = ["full_name", "phone_number", "address_line", "city", "state", "pincode"]
    return all(payload.get(field) for field in required_fields)


def _persist_address_payload(user, payload):
    selected_address_id = payload.get("selected_address_id")
    if selected_address_id:
        address = SavedAddress.objects.filter(id=selected_address_id, user=user).first()
        if address:
            address.label = payload["label"]
            address.full_name = payload["full_name"]
            address.phone_number = payload["phone_number"]
            address.address_line = payload["address_line"]
            address.landmark = payload["landmark"]
            address.city = payload["city"]
            address.state = payload["state"]
            address.pincode = payload["pincode"]
            address.save()
            return address

    address = SavedAddress.objects.create(
        user=user,
        label=payload["label"],
        full_name=payload["full_name"],
        phone_number=payload["phone_number"],
        address_line=payload["address_line"],
        landmark=payload["landmark"],
        city=payload["city"],
        state=payload["state"],
        pincode=payload["pincode"],
        is_default=not SavedAddress.objects.filter(user=user).exists(),
    )
    return address


def _delivery_fields_from_payload(payload):
    address_parts = [payload["address_line"], payload["landmark"], payload["city"], payload["state"], payload["pincode"]]
    return {
        "delivery_name": payload["full_name"],
        "delivery_phone": payload["phone_number"],
        "delivery_address": ", ".join([part for part in address_parts if part]),
        "delivery_map_query": payload["map_query"],
    }


def add_to_cart(request, dish_id):
    dish = _available_dishes_queryset().filter(id=dish_id).first()
    if not dish:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Dish not found."}, status=404)
        messages.warning(request, "Dish not found.")
        return redirect("shop")

    if request.user.is_authenticated:
        _merge_session_cart_to_db(request)
        cart_item = CartItem.objects.filter(user=request.user, dish=dish).first()
        if cart_item:
            cart_item.quantity += 1
            cart_item.save(update_fields=["quantity", "updated_at"])
        else:
            CartItem.objects.create(user=request.user, dish=dish, quantity=1)
        cart_count = _cart_count_for_request(request)
    else:
        cart = _get_cart(request)
        key = str(dish_id)
        cart[key] = cart.get(key, 0) + 1
        request.session["cart"] = cart
        request.session.modified = True
        cart_count = _cart_count(cart)
    messages.success(request, f"{dish.name} added to cart.")

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "message": f"{dish.name} added to cart.",
                "cart_count": cart_count,
            }
        )

    next_url = request.GET.get("next") or request.POST.get("next")
    return redirect(next_url or "shop")


def cart_page(request):
    items, total = _cart_items_with_total(request)
    saved_addresses = list(_saved_addresses_for_user(request.user)) if request.user.is_authenticated else []
    return render(
        request,
        "cart.html",
        {
            "items": items,
            "total": total,
            "saved_addresses": saved_addresses[:3],
        },
    )


def remove_from_cart(request, dish_id):
    if request.user.is_authenticated:
        _merge_session_cart_to_db(request)
        CartItem.objects.filter(user=request.user, dish_id=dish_id).delete()
        cart_count = _cart_count_for_request(request)
    else:
        cart = _get_cart(request)
        cart.pop(str(dish_id), None)
        request.session["cart"] = cart
        request.session.modified = True
        cart_count = _cart_count(cart)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        items, total = _cart_items_with_total(request)
        return JsonResponse(
            {
                "ok": True,
                "message": "Item removed from cart.",
                "cart_count": cart_count,
                "cart_total": float(total),
                "cart_empty": len(items) == 0,
                "items_count": len(items),
            }
        )
    return redirect("cart_page")


def update_cart_quantity(request, dish_id):
    dish = _available_dishes_queryset().filter(id=dish_id).first()
    if not dish:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Dish not available."}, status=404)
        messages.warning(request, "Dish not available.")
        return redirect("cart_page")

    action = (request.GET.get("action") or request.POST.get("action") or "").strip().lower()
    if request.user.is_authenticated:
        _merge_session_cart_to_db(request)
        cart_item = CartItem.objects.filter(user=request.user, dish_id=dish_id).first()
        current_qty = int(cart_item.quantity if cart_item else 0)
    else:
        cart = _get_cart(request)
        key = str(dish_id)
        current_qty = int(cart.get(key, 0) or 0)

    if current_qty <= 0:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Item not found in cart."}, status=404)
        return redirect("cart_page")

    if action == "increase":
        current_qty += 1
    elif action == "decrease":
        current_qty -= 1
    else:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Invalid cart action."}, status=400)
        return redirect("cart_page")

    if request.user.is_authenticated:
        if current_qty <= 0:
            if cart_item:
                cart_item.delete()
            quantity = 0
        else:
            cart_item.quantity = current_qty
            cart_item.save(update_fields=["quantity", "updated_at"])
            quantity = current_qty
    else:
        if current_qty <= 0:
            cart.pop(key, None)
            quantity = 0
        else:
            cart[key] = current_qty
            quantity = current_qty
        request.session["cart"] = cart
        request.session.modified = True
    items, total = _cart_items_with_total(request)
    line_total = float(dish.price) * quantity if quantity > 0 else 0

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "message": f"{dish.name} quantity updated.",
                "quantity": quantity,
                "line_total": line_total,
                "cart_total": float(total),
                "cart_count": _cart_count_for_request(request),
                "cart_empty": len(items) == 0,
                "items_count": len(items),
            }
        )

    return redirect("cart_page")


@login_required
def checkout_cart(request):
    items, total = _cart_items_with_total(request)
    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect("shop")

    saved_addresses = list(_saved_addresses_for_user(request.user))
    preferred_address_id = request.GET.get("address_id") or request.POST.get("selected_address_id")
    address_form = _default_address_data(request.user, saved_addresses, preferred_address_id=preferred_address_id)

    if request.method == "POST":
        address_form = _address_payload_from_post(request, request.user, saved_addresses)
        if not _validate_address_payload(address_form):
            messages.warning(request, "Please fill complete delivery address details.")
            return render(
                request,
                "checkout_cart.html",
                {
                    "items": items,
                    "total": total,
                    "saved_addresses": saved_addresses,
                    "saved_addresses_json": _serialize_addresses(saved_addresses),
                    "address_form": address_form,
                    "chef_location": items[0]["dish"].chef.location if items and items[0]["dish"] and items[0]["dish"].chef else "Ahmedabad",
                    "distance_km": None,
                    "route_map_url": _fallback_map_embed_url(address_form["map_query"]),
                },
            )

        if address_form["save_address"] or address_form["selected_address_id"]:
            saved_address = _persist_address_payload(request.user, address_form)
            address_form["selected_address_id"] = saved_address.id
            address_form["map_query"] = saved_address.map_query

        payment_method = request.POST.get("payment_method", "COD")
        created_order_ids = []
        delivery_fields = _delivery_fields_from_payload(address_form)

        for item in items:
            dish = item["dish"]
            qty = item["quantity"]
            line_total = item["line_total"]
            payment_status = (
                Order.PaymentStatus.PAID
                if payment_method in [Order.PaymentMethod.CARD]
                else Order.PaymentStatus.PENDING
            )
            order = Order.objects.create(
                buyer=request.user,
                dish=dish,
                quantity=qty,
                total_amount=line_total,
                payment_method=payment_method,
                payment_status=payment_status,
                **delivery_fields,
            )
            created_order_ids.append(order.id)

        created_orders = list(Order.objects.filter(id__in=created_order_ids).select_related("dish"))
        notify_order_placed(request.user, created_orders)
        notify_chef_order_placed(created_orders)
        if payment_method == Order.PaymentMethod.CARD:
            notify_payment_success(request.user, created_orders)

        CartItem.objects.filter(user=request.user).delete()
        request.session["cart"] = {}
        request.session["last_order_ids"] = created_order_ids
        request.session.modified = True

        if payment_method == Order.PaymentMethod.UPI:
            return redirect("upi_payment_bulk")

        return redirect("order_confirmation")

    return render(
        request,
        "checkout_cart.html",
        {
            "items": items,
            "total": total,
            "saved_addresses": saved_addresses,
            "saved_addresses_json": _serialize_addresses(saved_addresses),
            "address_form": address_form,
            "chef_location": items[0]["dish"].chef.location if items and items[0]["dish"] and items[0]["dish"].chef else "Ahmedabad",
            "distance_km": None,
            "route_map_url": _fallback_map_embed_url(address_form["map_query"]),
        },
    )


@login_required
def checkout(request, dish_id):
    dish = _available_dishes_queryset().select_related('chef').filter(id=dish_id).first()
    if not dish:
        messages.warning(request, "Dish not found or not available.")
        return redirect("shop")

    saved_addresses = list(_saved_addresses_for_user(request.user))
    preferred_address_id = request.GET.get("address_id") or request.POST.get("selected_address_id")
    address_form = _default_address_data(request.user, saved_addresses, preferred_address_id=preferred_address_id)

    if request.method == "POST":
        quantity = int(request.POST.get("quantity", 1))
        address_form = _address_payload_from_post(request, request.user, saved_addresses)
        if not _validate_address_payload(address_form):
            messages.warning(request, "Please fill complete delivery address details.")
            return render(
                request,
                "checkout.html",
                {
                    "dish": dish,
                    "saved_addresses": saved_addresses,
                    "saved_addresses_json": _serialize_addresses(saved_addresses),
                    "address_form": address_form,
                    "chef_location": dish.chef.location if dish and dish.chef else "Ahmedabad",
                    "distance_km": None,
                    "route_map_url": _fallback_map_embed_url(address_form["map_query"]),
                },
            )

        if address_form["save_address"] or address_form["selected_address_id"]:
            saved_address = _persist_address_payload(request.user, address_form)
            address_form["selected_address_id"] = saved_address.id
            address_form["map_query"] = saved_address.map_query

        payment_method = request.POST.get("payment_method", "COD")
        total_amount = dish.price * quantity
        delivery_fields = _delivery_fields_from_payload(address_form)

        payment_status = (
            Order.PaymentStatus.PAID
            if payment_method in [Order.PaymentMethod.CARD]
            else Order.PaymentStatus.PENDING
        )

        order = Order.objects.create(
            buyer=request.user,
            dish=dish,
            quantity=quantity,
            total_amount=total_amount,
            payment_method=payment_method,
            payment_status=payment_status,
            **delivery_fields,
        )

        messages.success(request, f"Order placed successfully. Order ID: {order.id}")
        notify_order_placed(request.user, [order])
        notify_chef_order_placed([order])
        if payment_method == Order.PaymentMethod.CARD:
            notify_payment_success(request.user, [order])
        if payment_method == Order.PaymentMethod.UPI:
            return redirect("upi_payment_single", order_id=order.id)
        return redirect("order_success", order_id=order.id)

    return render(
        request,
        "checkout.html",
        {
            "dish": dish,
            "saved_addresses": saved_addresses,
            "saved_addresses_json": _serialize_addresses(saved_addresses),
            "address_form": address_form,
            "chef_location": dish.chef.location if dish and dish.chef else "Ahmedabad",
            "distance_km": None,
            "route_map_url": _fallback_map_embed_url(address_form["map_query"]),
        },
    )


@login_required
def order_success(request, order_id):
    order = Order.objects.filter(id=order_id, buyer=request.user).select_related("dish", "dish__chef").first()
    if not order:
        messages.warning(request, "Order not found.")
        return redirect("shop")
    eta_time = timezone.localtime(timezone.now() + timedelta(minutes=35))
    india_now = _india_now()
    chef_location = order.dish.chef.location if order.dish and order.dish.chef else "Ahmedabad"
    customer_location = order.delivery_map_query or chef_location
    distance_km = _distance_km(chef_location, customer_location)
    quick_eta_minutes = _delivery_eta_from_distance(distance_km)
    return render(
        request,
        "order_success.html",
        {
            "order": order,
            "existing_review": getattr(order, "review", None),
            "eta_time": eta_time,
            "india_now": india_now,
            "chef_location": chef_location,
            "map_location": customer_location,
            "distance_km": distance_km,
            "quick_eta_minutes": quick_eta_minutes,
            "eta_destination_time": india_now + timedelta(minutes=quick_eta_minutes),
            "route_map_url": _route_map_url(chef_location, customer_location),
            "whatsapp_link": build_whatsapp_link(
                request.user.phone_number,
                f"Hi Cloud Chef, I placed order #{order.id} for {order.dish.name}. Please keep me updated.",
            ),
        },
    )


@login_required
@require_POST
def submit_order_review(request, order_id):
    order = Order.objects.filter(id=order_id, buyer=request.user).select_related("dish", "dish__chef").first()
    if not order:
        messages.error(request, "Order not found.")
        return redirect("past_orders")
    if order.is_cancelled:
        messages.warning(request, "Cancelled order par feedback nahi liya ja sakta.")
        return redirect("past_orders")

    rating = max(1, min(5, int(request.POST.get("rating", "5") or "5")))
    feedback = (request.POST.get("feedback") or "").strip()
    if not feedback:
        messages.warning(request, "Please share a short feedback.")
        return redirect("order_success", order_id=order.id)

    OrderReview.objects.update_or_create(
        order=order,
        defaults={
            "user": request.user,
            "dish": order.dish,
            "chef": order.dish.chef,
            "rating": rating,
            "feedback": feedback,
        },
    )
    order.review_prompt_disabled = True
    order.save(update_fields=["review_prompt_disabled"])
    messages.success(request, "Thanks for sharing your review.")
    return redirect("order_success", order_id=order.id)


@login_required
@require_POST
def dismiss_order_review_prompt(request, order_id):
    order = Order.objects.filter(id=order_id, buyer=request.user).first()
    if not order:
        return JsonResponse({"ok": False, "message": "Order not found."}, status=404)
    order.review_prompt_disabled = True
    order.save(update_fields=["review_prompt_disabled"])
    return JsonResponse({"ok": True})


@login_required
def order_confirmation(request):
    order_ids = request.session.get("last_order_ids", [])
    orders = Order.objects.filter(id__in=order_ids, buyer=request.user).select_related("dish", "dish__chef")
    if not orders.exists():
        messages.warning(request, "No recent order found.")
        return redirect("shop")

    total = sum([o.total_amount for o in orders])
    eta_time = timezone.localtime(timezone.now() + timedelta(minutes=40))
    india_now = _india_now()
    first_order = orders.first()
    chef_location = first_order.dish.chef.location if first_order and first_order.dish and first_order.dish.chef else "Ahmedabad"
    customer_location = first_order.delivery_map_query if first_order and first_order.delivery_map_query else chef_location
    distance_km = _distance_km(chef_location, customer_location)
    quick_eta_minutes = _delivery_eta_from_distance(distance_km)
    return render(
        request,
        "order_confirmation.html",
        {
            "orders": orders,
            "total": total,
            "eta_time": eta_time,
            "india_now": india_now,
            "delivery_name": first_order.delivery_name if first_order else "",
            "delivery_phone": first_order.delivery_phone if first_order else "",
            "delivery_address": first_order.delivery_address if first_order else "",
            "chef_location": chef_location,
            "map_location": customer_location,
            "distance_km": distance_km,
            "quick_eta_minutes": quick_eta_minutes,
            "eta_destination_time": india_now + timedelta(minutes=quick_eta_minutes),
            "route_map_url": _route_map_url(chef_location, customer_location),
            "whatsapp_link": build_whatsapp_link(
                request.user.phone_number,
                f"Hi Cloud Chef, my order is confirmed. Please share delivery updates with me.",
            ),
        },
    )


@login_required
def past_orders(request):
    orders = (
        Order.objects.filter(buyer=request.user)
        .select_related("dish", "dish__chef")
        .order_by("-id")
    )
    return render(request, "past_orders.html", {"orders": orders})


@login_required
@require_POST
def remove_past_order(request, order_id):
    order = (
        Order.objects.filter(id=order_id, buyer=request.user)
        .select_related("dish")
        .first()
    )
    if not order:
        messages.warning(request, "Order not found.")
        return redirect("past_orders")

    order.delete()
    messages.success(request, "Past order removed successfully.")
    return redirect("past_orders")


@login_required
def notification_center(request):
    notifications = list(Notification.objects.filter(user=request.user).order_by("-created_at"))
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    return render(
        request,
        "notification_center.html",
        {
            "notifications": notifications,
            "notification_total": len(notifications),
            "notification_unread_count": sum(1 for item in notifications if not item.is_read),
        },
    )


@login_required
@require_POST
def clear_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    messages.success(request, "All alerts cleared.")
    return redirect("notification_center")


@login_required
@require_POST
def cancel_order(request, order_id):
    order = Order.objects.filter(id=order_id, buyer=request.user).select_related("dish").first()
    if not order:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Order not found."}, status=404)
        messages.error(request, "Order not found.")
        return redirect("past_orders")

    if order.is_cancelled:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "This order is already cancelled."}, status=400)
        messages.warning(request, "This order is already cancelled.")
        return redirect("past_orders")

    if not order.can_cancel:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "You can cancel only within 1 minute of order confirmation."}, status=400)
        messages.warning(request, "You can cancel only within 1 minute of order confirmation.")
        return redirect("past_orders")

    order.is_cancelled = True
    order.cancelled_at = timezone.now()
    order.save(update_fields=["is_cancelled", "cancelled_at"])
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": f"Order #{order.id} cancelled successfully.", "redirect_url": "/orders/"})
    messages.success(request, f"Order #{order.id} cancelled successfully.")
    return redirect("past_orders")


@login_required
@require_POST
def cancel_recent_order_group(request):
    order_ids = request.session.get("last_order_ids", [])
    orders = list(Order.objects.filter(id__in=order_ids, buyer=request.user).select_related("dish"))
    if not orders:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "No recent order found."}, status=404)
        messages.error(request, "No recent order found.")
        return redirect("past_orders")

    if any(order.is_cancelled for order in orders):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "This order is already cancelled."}, status=400)
        messages.warning(request, "This order is already cancelled.")
        return redirect("past_orders")

    if any(not order.can_cancel for order in orders):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "You can cancel only within 1 minute of order confirmation."}, status=400)
        messages.warning(request, "You can cancel only within 1 minute of order confirmation.")
        return redirect("past_orders")

    cancelled_at = timezone.now()
    Order.objects.filter(id__in=[order.id for order in orders]).update(is_cancelled=True, cancelled_at=cancelled_at)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": "Entire order cancelled successfully.", "redirect_url": "/orders/"})
    messages.success(request, "Entire order cancelled successfully.")
    return redirect("past_orders")


@login_required
def reorder_order(request, order_id):
    order = (
        Order.objects.filter(id=order_id, buyer=request.user)
        .select_related("dish")
        .first()
    )
    if not order:
        messages.warning(request, "Order not found.")
        return redirect("past_orders")

    if not order.dish or not order.dish.is_available:
        messages.warning(request, "This dish is currently unavailable.")
        return redirect("past_orders")

    quantity = max(int(order.quantity or 1), 1)
    if request.user.is_authenticated:
        _merge_session_cart_to_db(request)
        cart_item = CartItem.objects.filter(user=request.user, dish=order.dish).first()
        if cart_item:
            cart_item.quantity += quantity
            cart_item.save(update_fields=["quantity", "updated_at"])
        else:
            CartItem.objects.create(user=request.user, dish=order.dish, quantity=quantity)
    else:
        cart = request.session.setdefault("cart", {})
        key = str(order.dish.id)
        cart[key] = cart.get(key, 0) + quantity
        request.session["cart"] = cart
        request.session.modified = True
    messages.success(request, f"{order.dish.name} added again to cart.")
    return redirect("cart_page")


def home_order_widget_partial(request):
    html = render(
        request,
        "partials/home_order_widget.html",
        _home_order_context(request.user),
    ).content.decode("utf-8")
    return JsonResponse({"html": html})


def live_state(request):
    cart_count = _cart_count_for_request(request)
    unread_notification_count = 0
    pending_notifications = []

    if getattr(request, "user", None) and request.user.is_authenticated:
        sync_delivery_notifications(request.user)
        active_scope = Notification.Scope.CHEF if request.session.get("login_mode") == "chef" else Notification.Scope.CUSTOMER
        visible_scopes = [active_scope, Notification.Scope.GLOBAL]
        unread_notification_count = Notification.objects.filter(
            user=request.user,
            is_read=False,
            scope__in=visible_scopes,
        ).count()
        pending_qs = list(
            Notification.objects.filter(
                user=request.user,
                shown_in_browser=False,
                scope__in=visible_scopes,
            ).order_by("-id")[:5]
        )
        pending_notifications = [
            {
                "id": item.id,
                "title": item.title,
                "message": item.message,
                "level": item.notification_type,
            }
            for item in pending_qs
        ]
        if pending_qs:
            Notification.objects.filter(id__in=[item.id for item in pending_qs]).update(shown_in_browser=True)

    return JsonResponse(
        {
            "ok": True,
            "cart_count": cart_count,
            "unread_notification_count": unread_notification_count,
            "pending_notifications": pending_notifications,
        }
    )


def featured_dishes_partial(request):
    html = render(
        request,
        "partials/featured_dishes_grid.html",
        {"featured_dishes": _featured_dishes_queryset()},
    ).content.decode("utf-8")
    return JsonResponse({"html": html})


def shop_dishes_partial(request):
    dishes = _available_dishes_queryset().select_related('chef').order_by('-id')
    search = request.GET.get("search")
    if search:
        dishes = dishes.filter(name__icontains=search)
    html = render(
        request,
        "partials/shop_dishes_grid.html",
        {"dishes": dishes},
    ).content.decode("utf-8")
    return JsonResponse({"html": html})


def _build_upi_link(amount, note):
    params = {
        "pa": getattr(settings, "UPI_ID", "merchant@upi"),
        "pn": getattr(settings, "UPI_NAME", "Cloud Chef"),
        "am": f"{amount:.2f}",
        "cu": "INR",
        "tn": note,
    }
    return "upi://pay?" + urlencode(params)


@login_required
def upi_payment_single(request, order_id):
    order = Order.objects.filter(id=order_id, buyer=request.user).select_related("dish").first()
    if not order:
        messages.warning(request, "Order not found.")
        return redirect("shop")

    if request.method == "POST":
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status"])
        messages.success(request, "UPI payment marked as successful.")
        notify_payment_success(request.user, [order])
        return redirect("order_success", order_id=order.id)

    upi_link = _build_upi_link(float(order.total_amount), f"CloudChef Order {order.id}")
    return render(
        request,
        "upi_payment.html",
        {
            "title": f"Pay for Order #{order.id}",
            "amount": order.total_amount,
            "upi_link": upi_link,
            "payee_vpa": getattr(settings, "UPI_ID", "merchant@upi"),
            "payee_name": getattr(settings, "UPI_NAME", "Cloud Chef"),
        },
    )


@login_required
def upi_payment_bulk(request):
    order_ids = request.session.get("last_order_ids", [])
    orders = Order.objects.filter(id__in=order_ids, buyer=request.user)
    if not orders.exists():
        messages.warning(request, "No recent cart order found.")
        return redirect("cart_page")

    total = sum([o.total_amount for o in orders])
    if request.method == "POST":
        orders.update(payment_status=Order.PaymentStatus.PAID)
        messages.success(request, "UPI payment marked as successful.")
        notify_payment_success(request.user, list(orders.select_related("dish")))
        return redirect("order_confirmation")

    first_order = orders.first()
    note = f"CloudChef Cart {first_order.id}" if first_order else "CloudChef Cart"
    upi_link = _build_upi_link(float(total), note)
    return render(
        request,
        "upi_payment.html",
        {
            "title": "Pay for Cart Order",
            "amount": total,
            "upi_link": upi_link,
            "payee_vpa": getattr(settings, "UPI_ID", "merchant@upi"),
            "payee_name": getattr(settings, "UPI_NAME", "Cloud Chef"),
        },
    )

def newsletter(request):
    return render(request, 'newsletter.html')
