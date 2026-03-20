from django.urls import path
from home import views

urlpatterns = [
    path('' , views.index , name="index"),
    path('login/' , views.login_page, name='login_page'),
    path('register/' , views.register, name='register'),
    path('logout/' , views.logout_user, name='logout_user'),
    path('dashboard/' , views.dashboard, name='dashboard'),
    path('help/' , views.help, name='help'),
    path('contactus/' , views.contactus, name='contactus'),
    path('aboutus/' , views.aboutus, name='aboutus'),
    path('services/' , views.services, name='services'),
    path('blog/' , views.blog, name='blog'),
    path('careers/' , views.careers, name='careers'),
    path('privacy-policy/' , views.privacy_policy, name='privacy_policy'),
    path('events/' , views.events, name='events'),
    path('shop/' , views.shop, name='shop'),
    path('newsletter/' , views.newsletter, name='newsletter'),

]