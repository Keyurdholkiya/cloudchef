from django.shortcuts import render, redirect, HttpResponse
from .models import chefsUser
from django.db.models import Q
from django.contrib import messages
from .utils import generateRandomToken, sendEmailToken
from django.contrib.auth import authenticate, login
import random
from .utils import sendOTPtoEmail
from django.contrib.auth.decorators import login_required
from .models import chefsUser, Chef, FoodImages # Ensure these matches your models.py

@login_required
def chef_profile_setup(request):
    if request.method == "POST":
        chef_name = request.POST.get('chef_name')
        description = request.POST.get('description')
        location = request.POST.get('location')
        price = request.POST.get('price')
        # Use getlist to handle multiple files from a single input field
        images = request.FILES.getlist('food_images') 

        # 1. Create the Chef profile linked to the logged-in user
        chef = Chef.objects.create(
            chef_owner=request.user,
            chef_name=chef_name,
            chef_description=description,
            location=location,
            service_price=price,
            chef_slug=chef_name.lower().replace(" ", "-") # Simple slug generation
        )

        # 2. Loop through uploaded images and save them
        for img in images:
            FoodImages.objects.create(chef=chef, image=img)

        messages.success(request, "Your chef profile and food details have been saved!")
        return redirect('shop') # Redirect to the shop/dashboard page

    return render(request, 'chef_profile_setup.html')


def login_page(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        chef_user_qs = chefsUser.objects.filter(email=email)

        if not chef_user_qs.exists():
            messages.warning(request, "No Account Found.")
            return redirect('login_page')

        chef_user = chef_user_qs.first()

        if not chef_user.is_verified:
            messages.warning(request, "Account not verified. Please check your email.")
            return redirect('login_page')

        # Authenticate using the username field (phone_number)
        user = authenticate(username=chef_user.username, password=password)

        if user:
            login(request, user)
            messages.success(request, "Login Successful!")
            return redirect('/')  # Redirect to home page after login

        messages.warning(request, "Invalid credentials.")
        return redirect('login_page')

    return render(request, 'login.html')

def register(request):
    if request.method == "POST":
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        phone_number = request.POST.get('phone_number')

        if chefsUser.objects.filter(Q(email=email) | Q(phone_number=phone_number)).exists():
            messages.warning(request, "An account already exists with this Email or Phone Number.")
            return redirect('register')

        chef_user = chefsUser.objects.create(
            username=phone_number,  # Set username to phone_number
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            email_token=generateRandomToken()
        )
        chef_user.set_password(password)
        chef_user.save()

        sendEmailToken(email, chef_user.email_token)
        messages.success(request, "Registration successful! An email has been sent to verify your account.")
        return redirect('login_page')

    return render(request, 'register.html')

def verify_email_token(request, token):
    try:
        chef_user = chefsUser.objects.get(email_token=token)
        chef_user.is_verified = True
        chef_user.save()
        messages.success(request, "Your email has been successfully verified. You can now log in.")
        return redirect('login_page')
    except chefsUser.DoesNotExist:
        return HttpResponse("<h2>Invalid Token or user does not exist.</h2>")
      
      

def send_otp(request, email):
    # Use .first() to get a single object or None
    chef_user = chefsUser.objects.filter(email=email).first()

    if not chef_user:
        messages.warning(request, "No account found with that email.")
        return redirect('login_page')

    # Generate a random 4-digit OTP
    otp = random.randint(1000, 9999)
    chef_user.otp = otp
    chef_user.save()  # Save the OTP to the user's record

    sendOTPtoEmail(email, otp)
    messages.success(request, f"An OTP has been sent to {email}.")
    # Redirect to the verification page, passing the email in the URL
    return redirect(f'/accounts/verify-otp/{email}/')


# accounts/views.py

def verify_otp(request, email):
    if request.method == "POST":
        otp = request.POST.get('otp')
        chef_user = chefsUser.objects.get(email=email) # Using your new model name

        if otp == chef_user.otp:
            login(request, chef_user)
            messages.success(request, "Verification Successful!")
            # Redirect to profile setup instead of home
            return redirect('chef_profile_setup') 
        else:
            messages.warning(request, "Wrong OTP.")
            return redirect('verify_otp', email=email)
    
    return render(request, 'verify_otp.html', {'email': email})

def chef_profile_setup(request):
    if request.method == "POST":
        # Logic to save Chef details and handle multiple images
        chef_name = request.POST.get('chef_name')
        description = request.POST.get('description')
        images = request.FILES.getlist('food_images') # Get multiple files

        chef = Chef.objects.create(
            chef_user=request.user,
            chef_name=chef_name,
            chef_description=description,
            # ... other fields
        )

        for img in images:
            FoodImages.objects.create(chef=chef, image=img)

        messages.success(request, "Chef profile created successfully!")
        return redirect('shop')

    return render(request, 'chef_profile_setup.html')