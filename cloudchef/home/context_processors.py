from accounts.models import Notification, CartItem, Dish
from django.utils import timezone
from django.db import models
from .notification_service import sync_delivery_notifications


def cart_context(request):
    cart = request.session.get("cart", {})
    cart_count = 0
    mini_cart_items = []
    if getattr(request, "user", None) and request.user.is_authenticated:
        if cart:
            valid_ids = []
            normalized = {}
            for dish_id, qty in cart.items():
                try:
                    dish_id_int = int(dish_id)
                    qty_int = int(qty)
                except (TypeError, ValueError):
                    continue
                if qty_int > 0:
                    valid_ids.append(dish_id_int)
                    normalized[dish_id_int] = qty_int
            if valid_ids:
                dishes = {
                    item.id: item
                    for item in Dish.objects.filter(id__in=valid_ids, is_available=True).filter(
                        models.Q(available_until__isnull=True) | models.Q(available_until__gt=timezone.now())
                    )
                }
                existing = {item.dish_id: item for item in CartItem.objects.filter(user=request.user, dish_id__in=dishes.keys())}
                for dish_id, qty in normalized.items():
                    if dish_id not in dishes:
                        continue
                    cart_item = existing.get(dish_id)
                    if cart_item:
                        cart_item.quantity += qty
                        cart_item.save(update_fields=["quantity", "updated_at"])
                    else:
                        CartItem.objects.create(user=request.user, dish_id=dish_id, quantity=qty)
            request.session["cart"] = {}
            request.session.modified = True
        user_cart_items = list(
            CartItem.objects.filter(user=request.user)
            .select_related("dish")
            .only("quantity", "dish__name", "dish__price", "dish__image")
            .order_by("-updated_at", "-id")
        )
        cart_count = sum(item.quantity for item in user_cart_items)
        mini_cart_items = [
            {
                "name": item.dish.name,
                "quantity": item.quantity,
                "price": item.dish.price,
                "image_url": item.dish.image.url if item.dish.image else "",
            }
            for item in user_cart_items[:3]
        ]
    else:
        for qty in cart.values():
            try:
                cart_count += int(qty)
            except (TypeError, ValueError):
                continue
        valid_ids = []
        normalized = {}
        for dish_id, qty in cart.items():
            try:
                dish_id_int = int(dish_id)
                qty_int = int(qty)
            except (TypeError, ValueError):
                continue
            if qty_int > 0:
                valid_ids.append(dish_id_int)
                normalized[dish_id_int] = qty_int
        if valid_ids:
            dishes = {
                item.id: item
                for item in Dish.objects.filter(id__in=valid_ids).only("name", "price", "image")
            }
            for dish_id in valid_ids[:3]:
                dish = dishes.get(dish_id)
                if not dish:
                    continue
                mini_cart_items.append(
                    {
                        "name": dish.name,
                        "quantity": normalized.get(dish_id, 1),
                        "price": dish.price,
                        "image_url": dish.image.url if dish.image else "",
                    }
                )
    valid_themes = {
        "light",
        "dark",
        "sunset",
        "forest",
        "ocean",
        "royal",
        "rose",
        "midnight",
        "mint",
        "latte",
    }
    theme = request.session.get("site_theme", "light")
    if theme not in valid_themes:
        theme = "light"
    theme_toast = request.session.pop("theme_toast", "")
    if theme_toast:
        request.session.modified = True
    notifications_enabled = False
    unread_notification_count = 0
    pending_notifications = []
    sound_theme = "classic"
    if getattr(request, "user", None) and request.user.is_authenticated:
        notifications_enabled = bool(getattr(request.user, "notification_enabled", False))
        sound_theme = getattr(request.user, "sound_theme", "classic") or "classic"
        sync_delivery_notifications(request.user)
        active_scope = Notification.Scope.CHEF if request.session.get("login_mode") == "chef" else Notification.Scope.CUSTOMER
        visible_scopes = [active_scope, Notification.Scope.GLOBAL]
        unread_notification_count = Notification.objects.filter(user=request.user, is_read=False, scope__in=visible_scopes).count()
        pending_qs = list(Notification.objects.filter(user=request.user, shown_in_browser=False, scope__in=visible_scopes)[:5])
        pending_notifications = [
            {
                "title": item.title,
                "message": item.message,
                "level": item.notification_type,
            }
            for item in pending_qs
        ]
        if pending_qs:
            Notification.objects.filter(id__in=[item.id for item in pending_qs]).update(shown_in_browser=True)
    return {
        "cart_count": cart_count,
        "mini_cart_items": mini_cart_items,
        "site_theme": theme,
        "theme_toast": theme_toast,
        "notifications_enabled": notifications_enabled,
        "unread_notification_count": unread_notification_count,
        "pending_notifications": pending_notifications,
        "sound_theme": sound_theme,
    }
