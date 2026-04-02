

from django.urls import path
from . import views

# Ensure this variable is named exactly 'urlpatterns'
urlpatterns = [
    path('login/', views.login_page, name='login_page'),
    path('chef-login/', views.chef_login_page, name='chef_login_page'),
    path('chef-logout/', views.chef_logout, name='chef_logout'),
    path('register/', views.register, name='register'),
    path('verify-account/<token>/', views.verify_email_token, name="verify_email_token"),
    # path('dashboard/', views.dashboard, name='dashboard'),
    path('send_otp/<str:email>/', views.send_otp, name="send_otp"),
    path('verify-otp/<str:email>/', views.verify_otp, name="verify_otp"),
    path('chef-setup/', views.chef_profile_setup, name='chef_profile_setup'),
    path('chef-side/', views.chef_side, name='chef_side'),
    path('chef-side/add-dish/', views.add_dish, name='add_dish'),
    path('chef-side/my-dishes/', views.chef_my_dishes, name='chef_my_dishes'),
    path('chef-side/my-dishes/<int:dish_id>/remove/', views.remove_dish, name='remove_dish'),
    path('chef-side/orders/', views.chef_orders, name='chef_orders'),
    path('chef-side/orders/clear/', views.clear_chef_orders, name='clear_chef_orders'),
    path('chef-side/orders/<int:order_id>/remove/', views.remove_chef_order, name='remove_chef_order'),
    path('chef-side/earnings/', views.chef_earnings, name='chef_earnings'),
    path('chef-side/profile/', views.chef_profile, name='chef_profile'),
    
]
