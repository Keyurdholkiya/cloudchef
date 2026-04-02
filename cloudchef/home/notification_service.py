import json
import base64
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from accounts.models import Notification, Order


def _normalize_phone(phone_number):
    phone_number = (phone_number or "").strip().replace(" ", "")
    if not phone_number:
        return ""
    if phone_number.startswith("whatsapp:"):
        return phone_number
    if phone_number.startswith("+"):
        return phone_number
    if phone_number.startswith("91") and len(phone_number) >= 12:
        return "+" + phone_number
    return "+91" + phone_number


def build_whatsapp_link(phone_number, message):
    normalized = _normalize_phone(phone_number)
    if normalized.startswith("whatsapp:"):
        normalized = normalized.replace("whatsapp:", "", 1)
    normalized = normalized.replace("+", "")
    if not normalized:
        return ""
    return f"https://wa.me/{normalized}?text={urlencode({'text': message})[5:]}"


def _post_json(url, token, payload):
    if not url or not token:
        return False
    try:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "CloudChef/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=8):
            return True
    except URLError:
        return False


def _post_form(url, auth_username, auth_password, payload):
    if not url or not auth_username or not auth_password:
        return False
    try:
        auth_value = base64.b64encode(f"{auth_username}:{auth_password}".encode("utf-8")).decode("utf-8")
        request = Request(
            url,
            data=urlencode(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {auth_value}",
                "User-Agent": "CloudChef/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=8):
            return True
    except URLError:
        return False


def _send_twilio_message(to_number, message, from_number):
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    if not account_sid or not auth_token or not from_number or not to_number:
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    return _post_form(
        url,
        account_sid,
        auth_token,
        {
            "To": to_number,
            "From": from_number,
            "Body": message,
        },
    )


def send_sms_notification(user, message):
    if not getattr(user, "phone_number", None):
        return False
    normalized_phone = _normalize_phone(user.phone_number)
    twilio_from = getattr(settings, "TWILIO_SMS_FROM", "")
    if _send_twilio_message(normalized_phone, message, twilio_from):
        return True
    payload = {
        "to": normalized_phone,
        "message": message,
        "sender_id": getattr(settings, "SMS_SENDER_ID", "CLOUDCHEF"),
    }
    return _post_json(
        getattr(settings, "SMS_API_URL", ""),
        getattr(settings, "SMS_API_TOKEN", ""),
        payload,
    )


def send_whatsapp_notification(user, message):
    if not getattr(user, "phone_number", None):
        return False
    normalized_phone = _normalize_phone(user.phone_number)
    twilio_whatsapp_from = getattr(settings, "TWILIO_WHATSAPP_FROM", "")
    if twilio_whatsapp_from:
        twilio_to = normalized_phone if normalized_phone.startswith("whatsapp:") else f"whatsapp:{normalized_phone}"
        if _send_twilio_message(twilio_to, message, twilio_whatsapp_from):
            return True
    payload = {
        "to": normalized_phone,
        "message": message,
    }
    return _post_json(
        getattr(settings, "WHATSAPP_API_URL", ""),
        getattr(settings, "WHATSAPP_API_TOKEN", ""),
        payload,
    )


def send_email_notification(user, subject, message):
    if not getattr(user, "email", None):
        return False
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@cloudchef.local")
    try:
        send_mail(subject, message, from_email, [user.email], fail_silently=False)
        return True
    except Exception:
        return False


def create_notification(user, title, message, notification_type=Notification.NotificationType.INFO, event_key=None, scope=Notification.Scope.CUSTOMER, send_external=True):
    if not user or not user.is_authenticated or not getattr(user, "notification_enabled", True):
        return None

    if event_key:
        existing = Notification.objects.filter(event_key=event_key).first()
        if existing:
            return existing

    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        scope=scope,
        event_key=event_key,
    )

    if send_external:
        send_sms_notification(user, f"{title}: {message}")
        send_whatsapp_notification(user, f"{title}: {message}")
    return notification


def notify_login_welcome(user):
    if not user:
        return
    display_name = user.first_name or user.email
    title = "Welcome Back"
    message = f"Hi {display_name}, welcome back to Cloud Chef. Fresh homemade meals are waiting for you."
    send_email_notification(user, "Welcome Back to Cloud Chef", message)
    send_whatsapp_notification(user, message)
    create_notification(
        user,
        title,
        message,
        Notification.NotificationType.SUCCESS,
        event_key=f"login-welcome-{user.id}-{timezone.localdate()}",
        scope=Notification.Scope.CUSTOMER,
    )


def notify_order_placed(user, orders):
    if not orders:
        return
    if len(orders) == 1:
        order = orders[0]
        create_notification(
            user,
            "Order Placed",
            f"Your order for {order.dish.name} has been placed successfully.",
            Notification.NotificationType.ORDER,
            event_key=f"order-placed-{order.id}",
            scope=Notification.Scope.CUSTOMER,
        )
    else:
        first_order = orders[0]
        create_notification(
            user,
            "Cart Order Placed",
            f"{len(orders)} items ordered successfully from Cloud Chef.",
            Notification.NotificationType.ORDER,
            event_key=f"order-placed-cart-{first_order.id}",
            scope=Notification.Scope.CUSTOMER,
        )


def notify_payment_success(user, orders):
    if not orders:
        return
    if len(orders) == 1:
        order = orders[0]
        create_notification(
            user,
            "Payment Received",
            f"Payment received for {order.dish.name}. Your order is confirmed.",
            Notification.NotificationType.PAYMENT,
            event_key=f"payment-success-{order.id}",
            scope=Notification.Scope.CUSTOMER,
        )
    else:
        first_order = orders[0]
        create_notification(
            user,
            "Payment Received",
            f"Payment received for {len(orders)} ordered items.",
            Notification.NotificationType.PAYMENT,
            event_key=f"payment-success-cart-{first_order.id}",
            scope=Notification.Scope.CUSTOMER,
        )


def notify_chef_order_placed(orders):
    for order in orders or []:
        chef_user = getattr(getattr(order.dish, "chef", None), "chef_owner", None)
        if not chef_user:
            continue
        create_notification(
            chef_user,
            "New Order Received",
            f"{order.buyer.first_name or order.buyer.email} ordered {order.dish.name} x{order.quantity}.",
            Notification.NotificationType.ORDER,
            event_key=f"chef-order-placed-{order.id}",
            scope=Notification.Scope.CHEF,
            send_external=False,
        )


def notify_chef_order_delivered(order):
    chef_user = getattr(getattr(order.dish, "chef", None), "chef_owner", None)
    if not chef_user:
        return
    create_notification(
        chef_user,
        "Order Delivered",
        f"{order.dish.name} for {order.buyer.first_name or order.buyer.email} has been delivered.",
        Notification.NotificationType.DELIVERY,
        event_key=f"chef-order-delivered-{order.id}",
        scope=Notification.Scope.CHEF,
        send_external=False,
    )


def sync_delivery_notifications(user):
    if not user or not user.is_authenticated or not getattr(user, "notification_enabled", True):
        return
    threshold = timezone.now() - timezone.timedelta(minutes=60)
    delivered_orders = (
        Order.objects.filter(
            buyer=user,
            created_at__lte=threshold,
            is_cancelled=False,
            delivery_notification_sent=False,
        )
        .select_related("dish")
        .order_by("-id")[:5]
    )
    for order in delivered_orders:
        create_notification(
            user,
            "Order Delivered",
            f"Your order for {order.dish.name} has been delivered.",
            Notification.NotificationType.DELIVERY,
            event_key=f"order-delivered-{order.id}",
            scope=Notification.Scope.CUSTOMER,
        )
        notify_chef_order_delivered(order)
        order.delivery_notification_sent = True
        order.save(update_fields=["delivery_notification_sent"])
