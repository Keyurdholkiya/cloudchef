import uuid
from django.core.mail import send_mail
from django.conf import settings

def generateRandomToken():
    return str(uuid.uuid4())

def sendEmailToken(email, token):
    subject = "Verify Your OYO Clone Account"
    message = f"""Hi, please verify your email account by clicking this link:
    http://127.0.0.1:8000/account/verify-account/{token}/
    """
    send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)

# ✨ New function for sending OTP
def sendOTPtoEmail(email, otp):
    subject = "OTP for Account Login"
    message = f"""Hi, use this OTP to log in to your OYO Clone account.
    Your OTP is: {otp}
    """
    send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
    
