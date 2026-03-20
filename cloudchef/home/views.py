from django.shortcuts import render, redirect
from django.contrib.auth import logout

def index(request):
    return render(request, 'index.html')

def login_page(request):
    return render(request, 'login.html')

def register(request):
    return render(request, 'register.html')

def logout_user(request):
    logout(request)
    return redirect('/')

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
    return render(request, 'shop.html')

def newsletter(request):
    return render(request, 'newsletter.html')
