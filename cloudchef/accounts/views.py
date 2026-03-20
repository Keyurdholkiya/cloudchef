from django.shortcuts import render, redirect, HttpResponse
from .models import HotelUser
from django.db.models import Q
from django.contrib import messages
from .utils import generateRandomToken, sendEmailToken
from django.contrib.auth import authenticate, login
import random
from .utils import sendOTPtoEmail


def login_page(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        hotel_user_qs = HotelUser.objects.filter(email=email)

        if not hotel_user_qs.exists():
            messages.warning(request, "No Account Found.")
            return redirect('/account/login/')

        hotel_user = hotel_user_qs.first()

        if not hotel_user.is_verified:
            messages.warning(request, "Account not verified. Please check your email.")
            return redirect('/account/login/')

        # Authenticate using the username field (phone_number)
        user = authenticate(username=hotel_user.username, password=password)

        if user:
            login(request, user)
            messages.success(request, "Login Successful!")
            return redirect('/')  # Redirect to home page after login

        messages.warning(request, "Invalid credentials.")
        return redirect('/account/login/')

    return render(request, 'login.html')

def register(request):
    if request.method == "POST":
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        phone_number = request.POST.get('phone_number')

        if HotelUser.objects.filter(Q(email=email) | Q(phone_number=phone_number)).exists():
            messages.warning(request, "An account already exists with this Email or Phone Number.")
            return redirect('/account/register/')

        hotel_user = HotelUser.objects.create(
            username=phone_number,  # Set username to phone_number
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            email_token=generateRandomToken()
        )
        hotel_user.set_password(password)
        hotel_user.save()

        sendEmailToken(email, hotel_user.email_token)
        messages.success(request, "Registration successful! An email has been sent to verify your account.")
        return redirect('/account/login/')

    return render(request, 'register.html')

def verify_email_token(request, token):
    try:
        hotel_user = HotelUser.objects.get(email_token=token)
        hotel_user.is_verified = True
        hotel_user.save()
        messages.success(request, "Your email has been successfully verified. You can now log in.")
        return redirect('/account/login/')
    except HotelUser.DoesNotExist:
        return HttpResponse("<h2>Invalid Token or user does not exist.</h2>")
      
      

def send_otp(request, email):
    # Use .first() to get a single object or None
    hotel_user = HotelUser.objects.filter(email=email).first()

    if not hotel_user:
        messages.warning(request, "No account found with that email.")
        return redirect('/account/login/')

    # Generate a random 4-digit OTP
    otp = random.randint(1000, 9999)
    hotel_user.otp = otp
    hotel_user.save()  # Save the OTP to the user's record

    sendOTPtoEmail(email, otp)
    messages.success(request, f"An OTP has been sent to {email}.")
    # Redirect to the verification page, passing the email in the URL
    return redirect(f'/account/verify-otp/{email}/')


# ✨ New view to verify the submitted OTP
def verify_otp(request, email):
    if request.method == "POST":
        otp = request.POST.get('otp')
        hotel_user = HotelUser.objects.get(email=email)

        # Check if the submitted OTP matches the one in the database
        if otp == hotel_user.otp:
            # OTP is correct, log the user in
            login(request, hotel_user)
            messages.success(request, "Login Successful!")
            return redirect('/')  # Redirect to home page after success
        else:
            messages.warning(request, "You have entered the wrong OTP.")
            return redirect(f'/account/verify-otp/{email}/')

    # For GET requests, just show the verification page
    return render(request, 'verify_otp.html', {'email': email})