

from django.urls import path
from . import views

# Ensure this variable is named exactly 'urlpatterns'
urlpatterns = [
    path('login/', views.login_page, name='login_page'),
    path('register/', views.register, name='register'),
    path('verify-account/<token>/', views.verify_email_token, name="verify_email_token"),
    # path('dashboard/', views.dashboard, name='dashboard'),
    path('send_otp/<str:email>/', views.send_otp, name="send_otp"),
    path('verify-otp/<str:email>/', views.verify_otp, name="verify_otp"),
    path('chef-setup/', views.chef_profile_setup, name='chef_profile_setup'),
    
]